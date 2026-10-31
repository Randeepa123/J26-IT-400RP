"""Side-effect-free inference using the model active at the requested timestamp."""
import numpy as np
import pandas as pd
from .config import CUTOFF

UNITS = {'temperature': '°C (daily mean in this dataset)', 'precipitation': 'mm (daily sum in this dataset)',
         'solar_mw': 'MW', 'shortwave_radiation': 'W/m²', 'is_holiday': '0 or 1'}

def features(data):
    result = []
    for name, unit in UNITS.items():
        if name not in data: continue
        values = data[name].dropna()
        if values.empty: continue
        result.append(dict(name=name, unit=unit, default=float(values.median()), minimum=float(values.min()), maximum=float(values.max()),
                           required=True, effect='Used only by structural adaptation' if name=='solar_mw' else 'Model input'))
    return result

def simulate(service, request):
    ts = pd.Timestamp(request.timestamp)
    if ts.tzinfo: ts = ts.tz_convert('Asia/Colombo').tz_localize(None)
    if ts < pd.Timestamp(CUTOFF) or ts > service.data.timestamp.max():
        raise ValueError('Simulation must be within the deployment period and available dataset end')
    specs = features(service.data)
    expected = {s['name'] for s in specs}
    if set(request.features) != expected:
        raise ValueError(f'Required features: {sorted(expected)}; missing/unknown features are not accepted')
    for spec in specs:
        value = request.features[spec['name']]
        if not np.isfinite(value) or not spec['minimum'] <= value <= spec['maximum']:
            raise ValueError(f"{spec['name']} must be finite and in [{spec['minimum']}, {spec['maximum']}]")
        if spec['name']=='is_holiday' and value not in [0,1]:
            raise ValueError('is_holiday must be 0 or 1')
    values = dict(request.features)
    if 'solar_mw' in values: values['solar_mw'] = float(np.clip(values['solar_mw'],0,1000))
    static, _ = service.infer(ts, values)
    adapted, strategy = service.infer(ts, values, True)
    return dict(timestamp=ts, static_generation_mw=static, adapted_generation_mw=adapted,
                difference_mw=adapted-static, difference_percent=(adapted-static)/abs(static)*100 if static else None,
                strategy=strategy, validation=['Frozen model state as available at the selected time; no learning or dataset updates.',
                'Observed-weather conditional estimate; weather is not forecast by this application.',
                'Solar has no effect on the static model or non-structural adaptations; model input clipped to 0–1000 MW.',
                'Defaults/ranges describe the dataset, not physical limits; provide a meaningful joint scenario.'])
