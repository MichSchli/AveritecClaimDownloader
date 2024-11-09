import argparse
import json
from code.averitec_dataset import AveritecDataset

parser = argparse.ArgumentParser(description='Load a dataset and save it as a single json file.')
parser.add_argument("--input_file", default="data/averifever_sightings.json", type=str)
parser.add_argument("--dataset_folder", default="data/keep_averifever", type=str)
parser.add_argument("--output_prefix", default="averifever", type=str)
parser.add_argument("--output_file", default="data/averifever.with_dates.json", type=str)

args = parser.parse_args()


dataset = AveritecDataset()
dataset.from_raw_json(args.input_file, start=0, end=None)
dataset.preload_json_claims(args.dataset_folder, output_prefix=args.output_prefix, exclusive=True)

dataset.remove_raw_html()
dataset.save_as_averitec_json(args.output_file)