import unittest
from core.logger import logger, setup_logger
from config import settings
import os

class TestInternationalization(unittest.TestCase):
    def setUp(self):
        settings.SETTINGS['language'] = 'es'
        settings.SETTINGS['log_level'] = 'INFO'
        setup_logger()

    def test_spanish_translation(self):
        logger.info(_("Base de datos inicializada con WAL y índices"))
        with open('logs/alerts.log', 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("Base de datos inicializada con WAL e índices", content)

    def tearDown(self):
        if os.path.exists('logs/alerts.log'):
            os.remove('logs/alerts.log')