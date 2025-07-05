import unittest
from unittest.mock import patch
from core.scanner import check_bucket_async, is_valid_bucket_name
import asyncio

class TestScanner(unittest.TestCase):
    @patch('core.scanner.aiohttp.ClientSession.get')
    async def test_check_bucket_public(self, mock_get):
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.read.return_value = b'<?xml version="1.0"?><ListBucketResult><Contents><Key>test.txt</Key></Contents></ListBucketResult>'
        result = await check_bucket_async("test-bucket")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "test-bucket")

    @patch('core.scanner.aiohttp.ClientSession.get')
    async def test_check_bucket_private(self, mock_get):
        mock_get.return_value.__aenter__.return_value.status = 403
        result = await check_bucket_async("private-bucket")
        self.assertIsNone(result)

    @patch('core.scanner.aiohttp.ClientSession.get')
    async def test_check_bucket_error(self, mock_get):
        mock_get.side_effect = aiohttp.ClientError("Error de red")
        result = await check_bucket_async("error-bucket")
        self.assertIsNone(result)

    def test_valid_bucket_name(self):
        self.assertTrue(is_valid_bucket_name("valid-bucket"))
        self.assertFalse(is_valid_bucket_name("invalid bucket!"))
        self.assertFalse(is_valid_bucket_name("ab"))
        self.assertFalse(is_valid_bucket_name("a" * 64))

if __name__ == '__main__':
    unittest.main()