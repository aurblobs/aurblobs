

class AurBlobsError(BaseException):
    pass


class PackageError(AurBlobsError):
    pass


class PackageDoesNotExist(PackageError):
    pass


class RepositoryError(AurBlobsError):
    pass
