import logging, sys
FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=FORMAT)
get_logger = logging.getLogger
