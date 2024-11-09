import argparse

from code.averitec_dataset import AveritecDataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Filter and reformat a file of fetched claim from the Google API.')
    parser.add_argument("--input_file", default="data/averifever_sightings.json", type=str)
    parser.add_argument("--output_prefix", default="averifever", type=str)
    parser.add_argument("--output_folder", default="data/averifever", type=str)
    parser.add_argument("--keep_folder", default="data/keep_averifever", type=str)
    parser.add_argument("--store_folder", default="data/store_averifever", type=str)
    parser.add_argument("--discard_folder", default="data/discard_averifever", type=str)
    args = parser.parse_args()

    dataset = AveritecDataset()
    dataset.from_raw_json(args.input_file, start=0, end=None)
    #dataset.preload_json_claims(args.output_folder, output_prefix=args.output_prefix)

    #dataset.mark_internal_refs(save_during=False, json_folder=args.output_folder, output_prefix=args.output_prefix)

    #dataset.add_different_aspect(
    #    json_folder=args.output_folder,
    #    output_prefix=args.output_prefix,
    #    different_aspect_file=args.different_aspect_file
    #)
    #dataset.add_entity_replace(json_folder=args.output_folder, output_prefix=args.output_prefix, entity_replace_file=args.entity_replace_file)
    #dataset.add_semantically_similar(json_folder=args.output_folder, output_prefix=args.output_prefix, semantically_similar_file=args.semantically_similar_file)

    #dataset.add_duplicate_claim_annotation(
    #    json_folder=args.output_folder,
    #    output_prefix=args.output_prefix,
    #    duplicate_claim_file=args.duplicate_claim_file
    #)

    #dataset.add_web_archive_links(json_folder=args.output_folder, output_prefix=args.output_prefix)
    #dataset.fetch_all_fact_checking_article_htmls(save_during=True, json_folder=args.output_folder, output_prefix=args.output_prefix)

    #dataset.statistic_summary(json_folder=args.output_folder, output_prefix=args.output_prefix)
    dataset.filter_and_split(json_folder=args.output_folder,
                             output_prefix=args.output_prefix,
                             keep_folder=args.keep_folder,
                             store_folder=args.store_folder,
                             discard_folder=args.discard_folder,
                             claim_count=2000,
                             false_limit=800,
                             true_limit=800)
