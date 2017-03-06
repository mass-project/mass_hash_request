import unittest
from httmock import urlmatch, HTTMock
from mass_hash_request import query_mass_for_hashes, query_mass_for_samples
from mass_hash_request import generate_file_structure
from mass_hash_request import load_configuration
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

        with open('tests/data/file_sample_list.json') as fp:
            self.sample_list_json = json.load(fp)

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

    def test_query_mass_for_samples(self):
        parameters = {'delivery_date__gte': '2017-01-01', 'file_size__lte': 1000}

        @urlmatch(netloc='localhost')
        def mass_server_mock(url, request):
            self.assertEqual('2017-01-01', request.original.params['delivery_date__gte'])
            self.assertEqual(1000, request.original.params['file_size__lte'])
            return json.dumps(self.sample_list_json).encode('utf-8')

        with HTTMock(mass_server_mock):
            results = query_mass_for_samples(parameters)

        for sample in self.sample_list_json['results']:
            self.assertEqual(sample, results[sample['id']]._to_json())

    def test_incompatible_query_parameters(self):
        parameters = {'delivery_date__gte': '2017-01-01', 'file_size__lte': 1000, 'uri__startswith': 'http://'}

        with self.assertRaises(SystemExit) as cm:
            query_mass_for_samples(parameters)

        self.assertEqual(cm.exception.code, 1)

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

    def test_create_config(self):
        default_config = {'base_url': 'http://localhost:5000/api/', 'api_key': '', 'hash': 'md5',
                          'hashes': ['md5', 'sha1', 'sha256', 'sha512'], 'directory': 'mhr_result'}

        with tempfile.TemporaryDirectory() as conf_dir:
            conf_path = conf_dir + '/config.json'
            created_config = load_configuration(conf_path)

            # Check if config is returned after creation
            self.assertEqual(default_config, created_config)

            # Load the config again to make sure it's also stored
            loaded_config = load_configuration(conf_path)
            self.assertEqual(default_config, loaded_config)

    def test_load_config(self):
        default_config = {"api_key": "12345abcd", "base_url": "http://localhost:5000/", "directory": "mhr_result",
                          "hash": "md5", "hashes": ["md5", "sha1", "sha256", "sha512"]}

        config = load_configuration('tests/data/test_config.json')
        self.assertEqual(default_config, config)
