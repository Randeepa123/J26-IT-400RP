"""Streamlit research dashboard; all research data comes through HTTP."""
import os
from datetime import datetime, time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from src.api_client import call, predictions, align, rolling, APIError

load_dotenv()
st.set_page_config(page_title='PUCSL Grid Drift Adaptation System',page_icon='⚡',layout='wide')
st.markdown('''<style>
.stApp {background:#f5f7fa;color:#15283f} h1,h2,h3 {color:#10243d}
[data-testid="stSidebar"] {background:#e8eef5}
[data-testid="stMetric"] {background:white;border:1px solid #dce4ed;border-radius:8px;padding:16px}
.block-container {padding-top:2rem;max-width:1600px}
</style>''',unsafe_allow_html=True)
st.title('PUCSL Grid Drift Adaptation System')
st.caption('Monitoring concept drift and evaluating cause-matched machine learning adaptation in Sri Lankan electricity generation.')
BASE=os.getenv('API_URL','http://127.0.0.1:8000').rstrip('/')

@st.cache_data(ttl=120,show_spinner=False)
def get(path,params=None): return call(BASE,path,params)

@st.cache_data(ttl=120,show_spinner=False)
def get_predictions(params,model): return predictions(BASE,params,model)

def table_download(data,name):
    frame=pd.DataFrame(data)
    if frame.empty: st.info('No records match these filters.')
    else: st.dataframe(frame,hide_index=True,width='stretch')
    st.download_button('Download CSV',frame.to_csv(index=False).encode(),file_name=name+'.csv',mime='text/csv',key=name)

def number(value,suffix=''):
    return 'N/A' if value is None or pd.isna(value) else f'{value:,.2f}{suffix}'

def markers(fig,events):
    for event in events:
        dt=pd.Timestamp(event['drift_date'])
        fig.add_shape(type='line',x0=dt,x1=dt,y0=0,y1=1,yref='paper',line=dict(color='#c38922',dash='dash',width=1))
        fig.add_trace(go.Scatter(x=[dt],y=[1],yaxis='y2',mode='markers',name='Detected drift',showlegend=False,
            marker=dict(symbol='diamond',color='#c38922',size=8),
            text=[f"{event['drift_type']} · {event['match_status']} · {event.get('historical_event') or 'No verified event'}"],
            hovertemplate='%{x}<br>%{text}<extra></extra>'))
    fig.update_layout(yaxis2=dict(overlaying='y',range=[0,1.1],visible=False))

def chart(frame,columns,events,ylabel):
    fig=go.Figure()
    colors={'actual_generation_mw':'#10243d','static':'#6984af','adapted':'#168d82'}
    labels={'actual_generation_mw':'Actual generation','static':'Static Baseline','adapted':'Cause-Matched Adapted'}
    stride=max(1,int(np.ceil(len(frame)/6000)))
    for col in columns:
        if col not in frame: continue
        sampled=frame.iloc[::stride]
        error_column=col+'_ape'
        error=sampled[error_column] if error_column in sampled else np.full(len(sampled),np.nan)
        fig.add_trace(go.Scattergl(x=sampled.timestamp,y=sampled[col],name=labels[col],mode='lines',
            customdata=error,line=dict(color=colors[col],width=1.3),
            hovertemplate='%{x}<br>%{y:.2f}<br>APE: %{customdata:.2f}%<extra>%{fullData.name}</extra>' if error_column in sampled else '%{x}<br>%{y:.2f}<extra>%{fullData.name}</extra>'))
    markers(fig,events)
    fig.update_layout(template='plotly_white',height=420,margin=dict(l=20,r=20,t=20,b=20),
        yaxis_title=ylabel,hovermode='x unified',legend=dict(orientation='h',y=1.12),
        xaxis=dict(rangeslider=dict(visible=True,thickness=.06)))
    st.plotly_chart(fig,width='stretch')

try:
    with st.sidebar:
        st.header('Research controls')
        if st.button('Refresh backend data'):
            st.cache_data.clear()
            st.rerun()
    health=get('/health')
except APIError as exc:
    st.error(str(exc))
    st.info('Start the backend in a separate terminal. If artifacts are missing, run `python -m src.prepare` first. Health details are available at http://127.0.0.1:8000/health.')
    st.stop()

st.caption(f"● Backend connected · Ready · {health['observations']:,} valid observations · Local time: Asia/Colombo")
with st.expander('Dataset quality and research protocol'):
    st.json(health['data_quality'])
    for warning in health['warnings']: st.write('• '+warning)
    st.write('Training:',health['configuration']['train_start'],'to',health['configuration']['train_end'])
    st.write('Evaluation:',health['configuration']['test_start'],'to',health['configuration']['test_end'])

with st.expander('Future generation forecast — next 24 hours / next 7 days',expanded=True):
    st.caption('15-minute estimates from the saved static and adapted models. Historical filters below do not affect this forecast.')
    horizon_label=st.radio('Forecast horizon',['Next 24 hours','Next 7 days'],horizontal=True,key='forecast_horizon')
    origin_label=st.selectbox('Forecast starts from',['Now (Asia/Colombo)','Latest dataset observation'],key='forecast_origin')
    st.info('Future weather is estimated from recent daily averages; solar uses a recent intraday profile. These assumptions are shown with the output and are not live weather forecasts.')
    try:
        forecast_result=get('/forecast',{'horizon_hours':24 if horizon_label=='Next 24 hours' else 168,
                                        'origin':'now' if origin_label=='Now (Asia/Colombo)' else 'dataset_end'})
        future=pd.DataFrame(forecast_result['data'])
        future['timestamp']=pd.to_datetime(future.timestamp)
        st.caption(f"Forecast: {forecast_result['start']} to {forecast_result['end']} · Last observed data: {forecast_result['data_as_of']} · {forecast_result['count']} intervals")
        for warning in forecast_result['warnings']: st.warning(warning)
        left,middle,right=st.columns(3)
        left.metric('Mean static forecast',number(future.static_generation_mw.mean(),' MW'))
        middle.metric('Mean adapted forecast',number(future.adapted_generation_mw.mean(),' MW'))
        right.metric('Peak adapted forecast',number(future.adapted_generation_mw.max(),' MW'))
        chart(future.rename(columns={'static_generation_mw':'static','adapted_generation_mw':'adapted'}),
              ['static','adapted'],[],'Forecast generation (MW)')
        st.write('Active adapted strategy:',forecast_result['adapted_strategy'])
        for assumption in forecast_result['assumptions']: st.caption(assumption)
        inputs=pd.json_normalize(future.assumed_features).add_prefix('assumed_')
        export=pd.concat([future.drop(columns=['assumed_features']),inputs],axis=1)
        export['data_as_of']=forecast_result['data_as_of']
        export['forecast_origin']=forecast_result['forecast_origin']
        export['feature_method']=forecast_result['feature_method']
        st.download_button('Download future forecast CSV',export.to_csv(index=False).encode(),
                           f"forecast_{forecast_result['horizon_hours']}h.csv",'text/csv',key='forecast_download')
        with st.expander('Forecast values and assumed inputs'):
            st.dataframe(export,hide_index=True,width='stretch')
    except APIError as exc:
        st.error(f'Future forecast unavailable: {exc}')

try:
    regimes=get('/regimes')['data']
    with st.sidebar:
        latest=pd.Timestamp(health['dataset_end']).date()
        earliest=pd.Timestamp(health['configuration']['test_start']).date()
        st.caption(f'Available observations: {health["dataset_start"]} – {health["dataset_end"]}')
        if st.button('Clear active filters'):
            for key in ['dates','regimes','model','drift_class','match_status']: st.session_state.pop(key,None)
            st.rerun()
        dates=st.date_input('Evaluation dates',value=(earliest,latest),min_value=earliest,max_value=latest,key='dates')
        selected=st.multiselect('Regimes',[r['regime'] for r in regimes],default=[r['regime'] for r in regimes],
            format_func=lambda x:x.replace('_',' ').title(),key='regimes')
        model=st.selectbox('Model comparison',['Compare Both','Static Baseline','Cause-Matched Adapted Model'],key='model')
        drift_class=st.selectbox('Drift annotation classification',['All','abrupt','gradual','structural','unclassified'],key='drift_class')
        match_status=st.selectbox('Drift annotation event match',['All','unknown','confirmed','plausible','unmatched'],key='match_status')
        st.caption('Event filters affect drift markers, drift count, event table, and recovery table. Error metrics use all observations in the selected dates and regimes.')
    if len(dates)!=2 or not selected:
        st.info('Select a complete date range and at least one regime.'); st.stop()
    params={'start_date':str(dates[0]),'end_date':str(dates[1]),'regimes':selected}
    event_params=dict(params)
    if drift_class!='All': event_params['drift_type']=drift_class
    if match_status!='All': event_params['match_status']=match_status
    models=['static','adapted'] if model=='Compare Both' else ['static' if model=='Static Baseline' else 'adapted']
    with st.spinner('Loading aligned evaluation observations…'):
        frame=align({m:get_predictions(params,m) for m in models})
        events=get('/drifts',event_params)['data']
        metric_data=get('/metrics',params)['data']
        recovery_response=get('/metrics/adaptation-lag',params)
        recovery_data=recovery_response['data']
        event_dates={str(pd.Timestamp(e['drift_date'])) for e in events}
        recovery_data=[r for r in recovery_data if str(pd.Timestamp(r['drift_date'])) in event_dates]
    overview,performance,drifts,recovery_tab,simulation=st.tabs(['Overview','Regime Performance','Drift Events','Adaptation Recovery','Simulation'])
    with overview:
        st.caption(f'{dates[0]} through {dates[1]} inclusive · {", ".join(selected)} · {len(frame):,} aligned observations')
        if frame.empty: st.info('No evaluated observations match the filters.')
        else:
            cards=st.columns(4)
            for i,metric in enumerate(['MAPE','RMSE']):
                with cards[i]:
                    for m in models:
                        value=frame[m+'_ape'].mean() if metric=='MAPE' else np.sqrt(((frame.actual_generation_mw-frame[m])**2).mean())
                        st.metric(f'{m.title()} {metric}',number(value,'%' if metric=='MAPE' else ' MW'))
            cards[2].metric('Peak observed solar',number(frame.solar_mw.max() if 'solar_mw' in frame else None,' MW'))
            cards[3].metric('Detected drift points',len(events))
            st.subheader('Generation and model predictions')
            chart(frame,['actual_generation_mw',*models],events,'Electricity generation (MW)')
            st.caption('Chart renders at most 6,000 samples per trace; all observations contribute to metrics and downloads. Drift diamonds show classification and match details on hover.')
            st.subheader('Rolling 14-day MAPE')
            chart(rolling(frame,models),models,events,'MAPE (%)')
            st.caption('Trailing 14-day error aggregation, minimum 96 valid nonzero observations. The first 14 days use only the selected range; this is not a forecast horizon. Regime filters can create gaps in aggregation.')
            st.download_button('Download filtered predictions',frame.to_csv(index=False).encode(),'predictions.csv','text/csv')
    with performance:
        st.caption('Static and adapted metrics use identical timestamp-aligned test observations. Positive improvement means lower adapted MAPE; null means unavailable.')
        table_download(metric_data,'regime_metrics')
        usable=[r for r in metric_data if r['observations'] and r['regime'] in selected]
        if usable:
            worst=max(usable,key=lambda r:r['adapted_mape'])
            st.info(f"Highest adapted MAPE in this selection: {worst['regime']} ({worst['adapted_mape']:.2f}%).")
        else: st.info('Insufficient evidence for a regime insight.')
    with drifts:
        st.caption('Historical matches require recorded supporting evidence. No historical catalogue is bundled.')
        table_download(events,'drift_events')
    with recovery_tab:
        st.caption(recovery_response['methodology'])
        st.caption('Recovery uses the complete chronological series; date filters select events. Filtered-out dates do not change recovery calculations.')
        table_download(recovery_data,'adaptation_recovery')
        recovered=[r for r in recovery_data if r['lag_days'] is not None]
        if recovered:
            longest=max(recovered,key=lambda r:r['lag_days'])
            st.info(f"Longest measured recovery: {longest['lag_days']:.1f} days after {longest['drift_date']}.")
        else: st.info('Sustained recovery has not been observed for the selected events.')
    with simulation:
        st.subheader('Custom environmental scenario')
        specs=get('/simulation/features')['data']
        st.caption('Uses the frozen model active at the selected time. Inputs do not update any model or historical observation.')
        with st.form('scenario'):
            left,right=st.columns(2)
            sim_date=left.date_input('Scenario date',latest,min_value=earliest,max_value=latest)
            sim_time=right.time_input('Scenario time',time(0,0))
            values={}
            columns=st.columns(3)
            for i,spec in enumerate(specs):
                with columns[i%3]:
                    label=spec['name'].replace('_',' ').title()+' · '+spec['unit']
                    if spec['minimum']==spec['maximum']:
                        values[spec['name']]=spec['default']; st.caption(f'{label}: {spec["default"]} (constant)')
                    elif spec['name']=='is_holiday': values[spec['name']]=float(st.selectbox(label,[0,1],index=int(spec['default'])))
                    else: values[spec['name']]=st.number_input(label,min_value=spec['minimum'],max_value=spec['maximum'],value=spec['default'])
            submitted=st.form_submit_button('Run model simulation')
        if submitted:
            result=call(BASE,'/simulate',payload={'timestamp':datetime.combine(sim_date,sim_time).isoformat(),'features':values})
            a,b,c=st.columns(3)
            a.metric('Static prediction',number(result['static_generation_mw'],' MW'))
            b.metric('Adapted prediction',number(result['adapted_generation_mw'],' MW'))
            c.metric('Adapted minus static',number(result['difference_mw'],' MW'),number(result['difference_percent'],'%'))
            st.write('Active strategy:',result['strategy'])
            for detail in result['validation']: st.caption(detail)
except APIError as exc:
    st.error(str(exc))
