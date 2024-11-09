from claim_downloader import *
import argparse

from code.averitec_dataset import AveritecDataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Filter and reformat a file of fetched claim from the Google API.')
    parser.add_argument("--raw_download_file", default="data/averifever_sightings.json", type=str)
    parser.add_argument("--dataset_folder", default="data/averifever", type=str)
    parser.add_argument("--days_since_last_dump", default=544, type=int)
    parser.add_argument("--output_prefix", default="averifever", type=str)
    args = parser.parse_args()

    print("Finding publishers...")
    all_pubs = find_many_publishers(max_age=args.days_since_last_dump)
    print("Finding claims...")
    claim_match_pairs = recent_sample(all_pubs, output_filename=args.raw_download_file, max_age=args.days_since_last_dump)
    print(f"Found {len(claim_match_pairs)} pairs")

    dataset = AveritecDataset()
    dataset.from_raw_json(args.raw_download_file, start=0, end=None)
    dataset.save_to_json(args.dataset_folder, args.output_prefix)

    dataset.statistic_summary(
        json_folder=args.dataset_folder,
        output_prefix=args.output_prefix
    )

    dataset.fetch_all_fact_checking_article_htmls(save_during=True,
                                                  json_folder=args.dataset_folder,
                                                  output_prefix=args.output_prefix)

    #dataset2 = AveritecDataset()
    #dataset2.from_raw_json(args.old_dataset_raw_file, start=0, end=None)

    dataset.mark_internal_refs(save_during=True,
                               json_folder=args.dataset_folder,
                               output_prefix=args.output_prefix,
                               #wrt=dataset2.iter_claims(json_folder=args.old_dataset_folder, output_prefix=args.output_prefix)
                               )

    dataset.add_web_archive_links(save_during=True,
                                  json_folder=args.dataset_folder,
                                  output_prefix=args.output_prefix
                                  )

    dataset.statistic_summary(
        json_folder=args.dataset_folder,
        output_prefix=args.output_prefix
    )
