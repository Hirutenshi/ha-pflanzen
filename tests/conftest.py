"""Make HA's test loader see this repo's custom_components.

pytest-homeassistant-custom-component imports its own (empty) custom_components
package before the tests run, so ours is added to that package's search path.
"""

from pathlib import Path

import custom_components

_OURS = str(Path(__file__).parents[1] / "custom_components")
if _OURS not in custom_components.__path__:
    custom_components.__path__.insert(0, _OURS)
