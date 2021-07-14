from dataclasses import dataclass
from word_segmentation.beamsearch.algorithm import Beamsearch
from word_segmentation.beamsearch.reranker import Reranker
from word_segmentation.evaluation.utils import evaluate_dictionary
from word_segmentation.ensemble.top2_fusion import top2_ensemble
from dataclasses import dataclass, field
from transformers import HfArgumentParser
import logging 
import transformers
import datasets 
from datasets import load_dataset
logger = logging.getLogger(__name__)
import os 
import sys

@dataclass
class DataArguments:

    source: str = field(
        default='./Test-BOUN'
    )

    evaluate_top_k: int = field(
        default=10
    )

@dataclass
class BeamsearchArguments:
    
    decoder_model_name_or_path: str = field(
        default='gpt2-large'
    )

    decoder_model_type: str = field(
        default='gpt2'
    )

    decoder_device: str = field(
        default='cuda'
    )

    decoder_gpu_batch_size: int = field(
        default=1
    )

    topk: int = field(
        default=20
    )

    steps: int = field(
        default=13
    )

@dataclass
class RerankerArguments:

    encoder_model_name_or_path: str = field(
        default="bert-large-cased-whole-word-masking",
    )

    encoder_model_type: str = field(
        default="bert"
    )

@dataclass
class EnsembleArguments:

    alpha: float = field(
        default=0.2
    )

    beta: float = field(
        default=0.1
    )

def main():
    parser = HfArgumentParser((BeamsearchArguments, RerankerArguments, EnsembleArguments, DataArguments))
    if len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
        # If we pass only one argument to the script and it's the path to a json file,
        # let's parse it to get our arguments.
        beamsearch_args, reranker_args, ensemble_args, data_args = \
            parser.parse_json_file(json_file=os.path.abspath(sys.argv[1]))
    else:
        beamsearch_args, reranker_args, ensemble_args, data_args = \
            parser.parse_args_into_dataclasses()

    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logger.setLevel('DEBUG')
    datasets.utils.logging.set_verbosity('DEBUG')
    transformers.utils.logging.set_verbosity('DEBUG')
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()

    gpt2_model = Beamsearch(
        model_name_or_path=beamsearch_args.decoder_model_name_or_path,
        model_type=beamsearch_args.decoder_model_type,
        device=beamsearch_args.decoder_device,
        gpu_batch_size=beamsearch_args.decoder_gpu_batch_size
    )

    bert_model = Reranker(
        encoder_model_name_or_path=reranker_args.encoder_model_name_or_path,
        encoder_model_type=reranker_args.encoder_model_type
    )

    dataset = load_dataset('text', data_files={'test': data_args.source})
    gold = dataset['test'].to_dict()['text']
    hashtags = [x.replace(" ", "") for x in gold]

    gpt2_run = gpt2_model.run(
        hashtags,
        topk=beamsearch_args.topk,
        steps=beamsearch_args.steps
    )

    gpt2_candidates = gpt2_run.get_segmentations(
        astype='list'
    )

    gpt2_metrics = evaluate_dictionary(
        gpt2_candidates,
        gold,
        n=data_args.evaluate_top_k
    )

    logger.info("Beamsearch metrics:")
    logger.info("%s", gpt2_metrics)

    bert_run = bert_model.rerank(gpt2_run)

    ensemble = top2_ensemble(
        bert_run,
        gpt2_run,
        alpha=ensemble_args.alpha,
        beta=ensemble_args.beta,
        return_dataframe=False
    )

    candidates = list(ensemble.values())

    ensemble_metrics = evaluate_dictionary(
        candidates,
        gold,
        n=2
    )

    logger.info("Ensemble metrics:")
    logger.info("%s", ensemble_metrics)

if __name__ == '__main__':
    main()