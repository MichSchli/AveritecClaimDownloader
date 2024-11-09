import argparse

from code.averitec_dataset import AveritecDataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Filter and reformat a file of fetched claim from the Google API.')
    parser.add_argument("--input_file", default="fce_sightings.json", type=str)
    parser.add_argument("--dataset_1", default="dataset", type=str)
    parser.add_argument("--dataset_2", default="zhijiang_files/dataset", type=str)
    parser.add_argument("--output_folder", default="merged_dataset", type=str)
    parser.add_argument("--output_prefix", default="averitec", type=str)
    args = parser.parse_args()

    dataset_1 = AveritecDataset()
    dataset_1.from_raw_json(args.input_file, start=0, end=18000)

    dataset_2 = AveritecDataset()
    dataset_2.from_raw_json(args.input_file, start=18000, end=None)

    dataset_1.write(claim_folder=args.dataset_1, output_folder=args.output_folder, output_prefix=args.output_prefix)
    dataset_2.write(claim_folder=args.dataset_2, output_folder=args.output_folder, output_prefix=args.output_prefix)