from .management.commands.dump_masked_data import (
    Command as BasePostgresDataMaskingCommand,
)

__all__ = ["BasePostgresDataMaskingCommand"]
