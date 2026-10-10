from whitenoise.storage import CompressedManifestStaticFilesStorage


class FallbackStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Hashed static URLs when collectstatic output is present; plain URLs otherwise.

    On Vercel the collected files may not be bundled into the function, and a missing
    manifest would otherwise turn every page into a 500. WHITENOISE_USE_FINDERS then
    serves the plain-named files straight from ./static.
    """

    manifest_strict = False

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name
