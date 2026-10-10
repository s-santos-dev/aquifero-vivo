from app.scenarios.schemas import FactorChange


def difference(current, baseline):
    return current - baseline if current is not None and baseline is not None else None


def compare(baseline, hypothetical):
    delta = difference(hypothetical.score, baseline.score)
    relative = delta / baseline.score * 100 if delta is not None and baseline.score else None
    before = {f.group: f for f in baseline.factors}
    changes = []
    for factor in hypothetical.factors:
        original = before[factor.group]
        change = difference(factor.subscore, original.subscore)
        state = "indisponível" if change is None else "aumentou" if change > 1e-9 else "diminuiu" if change < -1e-9 else "permaneceu estável"
        changes.append(FactorChange(group=factor.group, name=factor.name, baseline=original.subscore,
                                   hypothetical=factor.subscore, delta_points=change,
                                   contribution_delta=difference(factor.contribution, original.contribution),
                                   explanation=f"{factor.name}: subscore {state}. {factor.explanation}"))
    changes.sort(key=lambda f: abs(f.contribution_delta or 0), reverse=True)
    return delta, relative, changes
