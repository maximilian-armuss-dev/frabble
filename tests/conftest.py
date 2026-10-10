"""Keep provider metadata loading offline, including in spawned test processes."""

import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
