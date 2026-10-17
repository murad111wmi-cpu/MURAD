"""Read persistent key material; never manufacture entropy from a weak key."""

def configured_secret_key(environment):
    primary = environment.get('DJANGO_SECRET_KEY')
    if not primary:
        return None
    extra = environment.get('DJANGO_SECRET_KEY_EXTRA')
    # Render generates each part independently. Both must stay stable across
    # builds and restarts. Existing single-key deployments remain unchanged.
    return primary + ':' + extra if extra else primary
