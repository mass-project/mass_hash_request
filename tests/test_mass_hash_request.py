import unittest
from httmock import urlmatch, HTTMock
from mass_hash_request import query_mass_for_hashes
from mass_hash_request import generate_file_structure
from mass_api_client.resources import FileSample, Report
from mass_api_client import ConnectionManager
import json
import tempfile
import os


class MassHashRequestTestCase(unittest.TestCase):
    class Options:
        print_missing = False

    def setUp(self):
        ConnectionManager().register_connection('default', '', 'http://localhost/api/')

        with open('tests/data/file_sample.json') as fp:
            data = FileSample._deserialize(json.load(fp))
            self.file_sample = FileSample._create_instance_from_data(data)

        with open('tests/data/report.json') as fp:
            data = Report._deserialize(json.load(fp))
            self.report = Report._create_instance_from_data(data)

    def test_query_mass_for_hashes(self):
        hash_type = 'md5'
        hashes = [
            'ffff',
            'aaaa',
        ]

        @urlmatch(netloc='localhost')
        def mass_server_mock(url, request):
            response = {'ffff': {
                "results": [self.file_sample._to_json()]
            }, 'aaaa': {'results': []}}
            hash_query = request.original.params['md5sum']
            return json.dumps(response[hash_query]).encode('utf-8')

        with HTTMock(mass_server_mock):
            results = query_mass_for_hashes(hash_type, hashes)

        self.assertEqual(results['ffff'].file_names[0], 'file.pdf')
        self.assertIsNone(results['aaaa'])

    def test_generate_file_structure(self):
        reports = {
            'results': [
                self.report._to_json()
            ]
        }
        query_results = {
            'ffff': self.file_sample,
            'aaaa': None
        }
        report_object = {'hello': 'world'}

        @urlmatch(netloc='localhost', path='/api/sample/ffff/reports/')
        def report_request(url, request):
            return json.dumps(reports).encode('utf-8')

        @urlmatch(netloc='localhost', path='/api/sample/ffff/download/')
        def download_request(url, request):
            return 'file_content'.encode('utf-8')

        @urlmatch(netloc='localhost', path='/api/report/ffff_report/json_report_object/some_report/')
        def report_object_request(url, request):
            return json.dumps(report_object).encode('utf-8')

        with tempfile.TemporaryDirectory() as base_dir:
            with HTTMock(report_request, download_request, report_object_request):
                options = self.Options()
                generate_file_structure(base_dir, query_results, options)

            self.assertTrue(os.path.exists(base_dir + '/ffff/Sample/file.pdf'))
            self.assertTrue(os.path.exists(base_dir + '/ffff/Reports/some_system/some_report.json'))
            self.assertTrue(os.path.exists(base_dir + '/aaaa/SampleNotFound'))
