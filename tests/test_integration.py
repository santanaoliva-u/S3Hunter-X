import unittest
import sqlite3
import os
from unittest.mock import patch
import asyncio
import aiohttp
from main import main
from config import settings

class TestIntegration(unittest.TestCase):
    def setUp(self):
        os.makedirs('data/downloads', exist_ok=True)
        with open('data/test_buckets.txt', 'w', encoding='utf-8') as f:
            f.write("test-bucket\n")
        with open('data/grep_words.txt', 'w', encoding='utf-8') as f:
            f.write("password\n")
        settings.SETTINGS['buckets_file'] = 'data/test_buckets.txt'
        settings.SETTINGS['patterns_file'] = 'data/grep_words.txt'

    @patch('core.scanner.aiohttp.ClientSession.get')
    async def test_full_workflow(self, mock_get):
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.read.return_value = b'<?xml version="1.0"?><ListBucketResult><Contents><Key>password.txt</Key></Contents></ListBucketResult>'
        await main()
        self.assertTrue(os.path.exists('results.md'))
        self.assertTrue(os.path.exists('results.json'))
        self.assertTrue(os.path.exists('results.json.gz'))
        self.assertTrue(os.path.exists('data/downloads/test-bucket/password.txt'))
        with sqlite3.connect('data/results.db') as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM results WHERE bucket = 'test-bucket' AND filename = 'password.txt'")
            self.assertIsNotNone(c.fetchone())

    @patch('core.scanner.aiohttp.ClientSession.get')
    async def test_empty_bucket(self, mock_get):
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.read.return_value = b'<?xml version="1.0"?><ListBucketResult></ListBucketResult>'
        await main()
        self.assertTrue(os.path.exists('results.md'))
        with open('results.md', 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("Archivos analizados: 0", content)

    @patch('core.scanner.aiohttp.ClientSession.get')
    async def test_network_error(self, mock_get):
        mock_get.side_effect = aiohttp.ClientError("Error de red")
        await main()
        self.assertTrue(os.path.exists('logs/alerts.log'))
        with open('logs/alerts.log', 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("Error al escanear", content)

    def tearDown(self):
        for file in ['data/test_buckets.txt', 'data/grep_words.txt', 'results.md', 'results.json', 'results.json.gz', 'data/results.db', 'logs/alerts.log']:
            if os.path.exists(file):
                os.remove(file)
        if os.path.exists('data/downloads'):
            import shutil
            shutil.rmtree('data/downloads')