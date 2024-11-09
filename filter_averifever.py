import argparse

from code.averitec_dataset import AveritecDataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Filter and reformat a file of fetched claim from the Google API.')
    parser.add_argument("--input_file", default="data/averifever_sightings.json", type=str)
    parser.add_argument("--output_prefix", default="averifever", type=str)
    parser.add_argument("--download_folder", default="data/averifever", type=str)
    parser.add_argument("--keep_folder", default="data/keep_averifever", type=str)
    parser.add_argument("--store_folder", default="data/store_averifever", type=str)
    parser.add_argument("--discard_folder", default="data/discard_averifever", type=str)
    parser.add_argument("--filter_folder", default="data/filter_averifever", type=str)
    args = parser.parse_args()

    dataset = AveritecDataset()
    dataset.from_raw_json(args.input_file, start=0, end=None)
    dataset.preload_json_claims(args.download_folder, output_prefix=args.output_prefix)

    #dataset.statistic_summary()

    dataset.delete_error_claims()
    dataset.delete_claims_with_no_archive_link()
    dataset.delete_long_and_short_claims()
    dataset.delete_duplicate_claims()

    dataset.filter_and_split(json_folder=None,
                             output_prefix=args.output_prefix,
                             keep_folder=args.keep_folder,
                             store_folder=args.store_folder,
                             discard_folder=args.discard_folder,
                             claim_count=2000,
                             false_limit=800,
                             true_limit=800)
    
    # Todo: Handle blocklist
