def reserve(available, requested):
    if requested <= 0:
        raise ValueError('Quantity must be positive')
    if requested >= available:
        return None
    return available - requested
