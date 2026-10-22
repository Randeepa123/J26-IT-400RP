"""HTTP-only dashboard access, with independent, testable transformations."""
import requests
import pandas as pd

class APIError(RuntimeError):
    pass

def call(base, path, params=None, payload=None):
    try:
        response = requests.post(base+path,json=payload,timeout=60) if payload is not None else requests.get(base+path,params=params,timeout=60)
        body = response.json()
        if not response.ok:
            raise APIError(body.get('error',{}).get('message') or '; '.join(body.get('warnings',[])) or str(body))
        return body
    except (requests.RequestException, ValueError) as exc:
        raise APIError(f'Backend unavailable or returned invalid JSON: {exc}') from exc

def predictions(base, params, model):
    rows, offset = [], 0
    while True:
        result = call(base,'/predict',{**params,'model_type':model,'offset':offset,'limit':50000})
        rows.extend(result['data'])
        offset += result['count']
        if offset >= result['total'] or not result['count']: break
    frame=pd.DataFrame(rows)
    if not frame.empty: frame['timestamp']=pd.to_datetime(frame.timestamp)
    return frame

def align(frames):
    result=None
    for model, frame in frames.items():
        if frame.empty: continue
        current=frame.rename(columns={'predicted_generation_mw':model,'ape_percent':model+'_ape'})
        if result is None: result=current
        else: result=result.merge(current[['timestamp',model,model+'_ape']],on='timestamp',validate='one_to_one',how='inner')
    return result if result is not None else pd.DataFrame()

def rolling(frame, models, minimum=96):
    if frame.empty: return frame.copy()
    indexed=frame.set_index('timestamp').sort_index()
    return pd.DataFrame({m:indexed[m+'_ape'].rolling('14D',min_periods=minimum).mean() for m in models}).reset_index()
