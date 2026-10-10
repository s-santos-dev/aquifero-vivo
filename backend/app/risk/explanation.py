def explain(name, inputs, available):
    if not available:
        missing = ", ".join(item.indicator for item in inputs if item.normalized is None)
        return f"{name}: dados insuficientes em {missing}; ausência não equivale a risco zero."
    values = "; ".join(f"{item.indicator}: {item.value:g} {item.unit} → {item.normalized:.2f}/100" for item in inputs)
    return f"{name}: média dos critérios normalizados ({values}). Escala experimental."
