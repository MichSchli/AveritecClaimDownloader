import argparse

from code.averitec_dataset import AveritecDataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Filter and reformat a file of fetched claim from the Google API.')
    parser.add_argument("--input_file", default="data/averifever_sightings.json", type=str)
    parser.add_argument("--output_prefix", default="averifever", type=str)
    parser.add_argument("--dataset_folder", default="data/keep_averifever", type=str)
    args = parser.parse_args()

    dataset = AveritecDataset()
    dataset.from_raw_json(args.input_file, start=0, end=None)
    dataset.preload_json_claims(args.dataset_folder, output_prefix=args.output_prefix, exclusive=True)

    dataset.statistic_summary()