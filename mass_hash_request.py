#!/usr/bin/env python3 
import os
import argparse
import json
import requests
from collections import namedtuple
import re
import tarfile

def load_configuration(config_path):
    if not os.path.exists(config_path):
        print("configuration file not found.\ncreating config: config.json ")
        config = create_config()
        save_configuration(config, config_path)
    else:
        with open(config_path, "r") as fp:
            config = json.load(fp)
    return config

def create_config():
    config['base_url'] = 'http://localhost:8000/api/sample/'
    config['hash'] = 'md5'
    config['hashes'] = ['md5', 'sha1']
    config['directory'] = 'mmhr_result'
    return config

def save_configuration(config, config_path):
    with open(config_path, "w") as fp:
        json.dump(config, fp, indent=4, sort_keys=True)

def _parse_args():
    '''
    Parses the command line arguments.

    :return: Namespace with arguments.
    :rtype: Namespace
    '''
    description = '''mass_multi_hash_request
    Uses your favourite MASS server to request if samples with hash sums are
    saved.'''
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('hashfile', help='file containing hash sums')
    parser.add_argument('--hash-type')
    options = parser.parse_args()

    return options

def update_config_from_options(config, options):
    if options.hash_type:
        if options.hash_type in config['hashes']:
            config['hash'] = options.hash_type
        else:
            raise ValueError('{} is not a known hash.'.format(options.hash_type))

def read_hash_sums(filename):
    hashes = []
    with open(filename) as hash_file:
        for h in hash_file:
            hashes.append(h.strip())
    return hashes

def query_mass_for_hashes(mass_url, hash_type, hashes):
    request_url = '{}?{}={}'
    results = {}
    for h in hashes:
        url = request_url.format(mass_url , hash_type + 'sum', h)
        query_response = requests.get(url)
        response = json.loads(query_response.text)
        if response['results']:
            results[h] = response['results'][0]
        else:
            results[h] = None
    return results

def touch_path(path):
    if not os.path.exists(path):
        os.mkdir(path)

def generate_no_file_found_file(path):
    open(path + '/SampleNotFound', 'w').close()

def generate_report_dir(path, result):
    reports_path = path + '/Reports'
    if result['reports']:
        touch_path(reports_path)
        for report in result['reports']:
            report_response = requests.get(report)
            report = json.loads(report_response.text)
            analysis_system = re.search('/analysis_system/([^/]*)/', report['analysis_system']).group(1)
            report_path = '{}/{}.json'.format(reports_path, analysis_system)
            with open(report_path,'w') as report_file:
                report_file.write(json.dumps(report, indent=4))


def download_file(url, dest_path):
    response = requests.get(url)
    with open(dest_path, 'wb') as f:
        f.write(response.content)

def generate_sample_dirs(path, result):
    sample_path = path + '/Sample'
    touch_path(sample_path)
    file_url = '{}{}'.format(result['url'],'download_file')
    file_path = '{}/{}'.format(sample_path, result['file'])
    download_file(file_url, file_path)

def generate_file_dirs(path,result):
    generate_report_dir(path,result)
    generate_sample_dirs(path,result)

def generate_file_structure(base_dir, query_results):
    if not os.path.exists(base_dir):
        os.mkdir(base_dir)
    for h, result in query_results.items():
        path = base_dir + '/' + h
        touch_path(path)
        if result:
            generate_file_dirs(path, result)
        else:
            generate_no_file_found_file(path)

def make_archive(path):
    with tarfile.open('result_archive.tar.gz', 'w:gz') as tar:
        tar.add(path)

if __name__ == '__main__':
    config_path = 'config.json'
    config = load_configuration(config_path)
    options = _parse_args()
    update_config_from_options(config, options)
    hashes = read_hash_sums(options.hashfile)
    results = query_mass_for_hashes(config['base_url'], config['hash'], hashes)
    generate_file_structure(config['directory'], results)
    make_archive(config['directory'])

