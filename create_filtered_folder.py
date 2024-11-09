from claim_downloader import *
import argparse

from code.averitec_dataset import AveritecDataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create a version of a dataset folder with all filters applied.')
    parser.add_argument("--raw_download_file", default="data/new_sightings.json", type=str)
    parser.add_argument("--old_dataset_folder", default="data/new_sightings_oct2021", type=str)
    parser.add_argument("--new_dataset_folder", default="data/new_sightings_oct2021_filtered", type=str)
    parser.add_argument("--output_prefix", default="averitec", type=str)
    args = parser.parse_args()

    dataset = AveritecDataset()
    dataset.from_raw_json(args.raw_download_file, start=0, end=None)

    dataset.save_to_json(args.new_dataset_folder,
                         args.output_prefix,
                         load_from_existing_jsons=args.old_dataset_folder,
                         filter=True)