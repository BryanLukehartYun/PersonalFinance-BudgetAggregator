
from . import capital_one
from . import nfcu

# Auto-detection order matters — more specific checks should come first
PARSERS = [
    capital_one,
    nfcu,
]