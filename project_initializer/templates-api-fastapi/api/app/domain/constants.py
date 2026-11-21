"""Business limits shared by every layer.

Schemas, ORM columns, services and overlays all read these values, so each limit
has one definition. Alembic migrations deliberately keep their own literals: a
migration is a frozen snapshot of the schema at one point in time.
"""

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 100
# Bounds the cost of a deep OFFSET scan, which the database still walks row by row.
MAX_OFFSET = 10_000

# Canonical textual UUID, which is what the string primary keys hold.
ENTITY_ID_LENGTH = 36

ITEM_NAME_MAX_LENGTH = 100
ITEM_DESCRIPTION_MAX_LENGTH = 500
ITEM_PRICE_MAX = 1_000_000_000.0

EMAIL_MAX_LENGTH = 255
USERNAME_MAX_LENGTH = 50
PERSON_NAME_MAX_LENGTH = 100
PASSWORD_MIN_LENGTH = 8
# bcrypt silently ignores everything past 72 bytes, so longer passwords are refused.
PASSWORD_MAX_BYTES = 72
