import unittest
from httmock import urlmatch, HTTMock
from mass_hash_request import query_mass_for_hashes
from mass_hash_request import generate_file_structure
import json
import re
import tempfile
import os

class MassHashRequestTestCase(unittest.TestCase):
    def test_query_mass_for_hashes(self):
        mass_url = 'http://mass_server.de'
        hash_type = 'md5'
        hashes = [
                'ffff',
                'aaaa',
                ]

        @urlmatch(netloc='mass_server.de')
        def mass_server_mock(url, request):
            response = {}
            response['ffff'] = {
                "results" : [
                    { 
                        'file' : 'something_harmfull.exe',
                    }]
                }
            response['aaaa'] = { 'results' : [] }
            hash_query = re.search('=(.*)', url.query).group(1)
            return json.dumps(response[hash_query]).encode('utf-8')

        with HTTMock(mass_server_mock):
            results = query_mass_for_hashes( mass_url, hash_type, hashes)
        self.assertEqual(results['ffff']['file'], 'something_harmfull.exe')
        self.assertIsNone(results['aaaa'])

    def test_generate_file_structure(self):
        query_results = {
                'ffff' : {
                    'url' : 'http://mass_server.de/api/sample/ffff/',
                    'file' : 'something_harmfull.exe',
                    'reports':[ 
                        'http://mass_server.de/api/report/some_report',
                        ]
                    },
                'aaaa' : None
                }

        report = {
                'analysis_system' : 'http://mass_server.de/analysis_system/some_system/',
                'result' : 'highly dangerous',
                }


        @urlmatch(netloc='mass_server.de', path='/api/report/some_report')
        def report_request(url, request):
            return json.dumps(report).encode('utf-8')

        @urlmatch(netloc='mass_server.de', path='/api/sample/ffff/download_file')
        def download_request(url, request):
            return 'file_content'.encode('utf-8')

        with tempfile.TemporaryDirectory() as base_dir:
            with HTTMock(report_request, download_request):
                generate_file_structure(base_dir, query_results)
        
            self.assertTrue(os.path.exists(base_dir + '/ffff/Sample/something_harmfull.exe'))
            self.assertTrue(os.path.exists(base_dir + '/ffff/Reports/some_system.json'))
            self.assertTrue(os.path.exists(base_dir + '/aaaa/SampleNotFound'))
