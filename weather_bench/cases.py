"""Public fixtures and private reference recipes. Never mount this module in an agent.

Oracles use NumPy/stdlib arithmetic, never skill output or xarray transformations.
Inputs are deliberately synthetic diagnostic fixtures, not historical observations.
"""
from dataclasses import dataclass
from pathlib import Path
import math
import numpy as np
import xarray as xr
import cftime


@dataclass
class Case:
    id: str
    title: str
    brief: str
    challenge: str
    datasets: dict
    expected: dict
    recipe: list
    exports: dict
    edges: list
    forbidden: tuple = ()
    suite: str = "diagnostic-v2"
    source_notes: tuple = ()

    def public(self):
        public = {"id": self.id, "title": self.title, "brief": self.brief,
                "challenge": self.challenge, "inputs": [f"{k}.zarr" for k in self.datasets],
                "input_metadata": {name+".zarr": {"dimensions":dict(ds.sizes),
                    "variables":{v:{"dims":list(ds[v].dims),"attrs":dict(ds[v].attrs)} for v in ds.data_vars},
                    "coordinates":{c:[str(x) for x in np.atleast_1d(ds[c].values).flat] for c in ds.coords}}
                    for name,ds in self.datasets.items()},
                "answer_schema": {k: shape_description(v) for k, v in self.expected.items()},
                "fixture_kind": "synthetic diagnostic", "tolerance": {"atol": 1e-6, "rtol": 1e-6}}
        if self.suite != "diagnostic-v2":
            # Discovery is part of the task. Do not hand the agent the reviewer
            # diagnosis, coordinate inventory, or private reference recipe.
            public.pop("challenge")
            public.pop("input_metadata")
            public.update(suite=self.suite, source_notes=list(self.source_notes),
                          fixture_kind="synthetic operational workflow; not historical weather")
            if self.suite == 'end-to-end-v1':
                public['fixture_kind']='real archived forecasts; live source retrieval'
                public['tolerance']={'atol':1e-4,'rtol':1e-6}
        return public


def shape_description(value):
    if isinstance(value, list):
        return {"type": "array", "length": len(value), "items": shape_description(value[0]) if value else None}
    return {"type": "string" if isinstance(value, str) else "number"}


def dataset(values, dims, coords, name="precip", units="mm day-1", interval="1 day"):
    ds = xr.Dataset({name: (dims, np.asarray(values, dtype=float))}, coords=coords)
    attrs = {"units": units, "long_name": name}
    if interval:
        attrs["data_interval"] = interval
    if name in ("precip", "tp"):
        attrs["standard_name"] = "lwe_thickness_of_precipitation_amount" if units == "mm" else "lwe_precipitation_rate"
        if units=="kg m-2 s-1": attrs["standard_name"]="precipitation_flux"
    else:
        attrs["standard_name"] = "sea_surface_temperature" if name=="sst" else "air_temperature"
    ds[name].attrs = attrs
    for axis, standard, units_, letter in [("latitude", "latitude", "degrees_north", "Y"),
                                          ("longitude", "longitude", "degrees_east", "X"),
                                          ("time", "time", None, "T")]:
        if axis in ds.coords:
            ds[axis].attrs = {"standard_name": standard, "axis": letter}
            if units_:
                ds[axis].attrs["units"] = units_
    ds.attrs = {"Conventions": "CF-1.13", "weather_skills_history": "[]",
                "fixture_kind": "synthetic diagnostic; not real weather"}
    return ds


def dates(start, n):
    return np.datetime64(start, "ns") + np.arange(n) * np.timedelta64(1, "D")


def step(id, skill, inputs, output, *args):
    return {"id": id, "skill": skill, "inputs": inputs.split(), "output": output, "args": list(args)}


def cases(include_refined=False):
    result = []
    lat = [0., 30., 60.]
    lon = [30., 31., 32.]
    weights = np.cos(np.radians(lat))
    a = 1 + np.arange(16)[:, None, None] * .3 + np.arange(3)[None, :, None] * 2 + np.arange(3)[None, None, :]
    totals = [sum(float(a[d, i, j]) * weights[i] for d in range(w, w+7) for i in range(3) for j in range(2)) / (2*sum(weights)) for w in (0, 7)]
    result.append(Case("rainfall-completeness", "A regional rainfall brief with an incomplete final week",
        "Using rain.zarr, report complete 7-day precipitation totals for the inclusive box north=60, west=30, south=0, east=31. Weeks begin 2024-01-01 and advance every 7 days. Exclude periods with fewer than seven daily timestamps. Average each weekly total spatially with cosine(latitude) weights and equal longitude weights. Return dates (YYYY-MM-DD), totals_mm, and units='mm'.",
        "Clip the correct cells, retain rate semantics during aggregation, drop the two-day tail, and apply area weights.",
        {"rain": dataset(a, ("time","latitude","longitude"), {"time": dates("2024-01-01",16),"latitude":lat,"longitude":lon})},
        {"dates":["2024-01-01","2024-01-08"],"totals_mm":totals,"units":"mm"},
        [step("clip","clip-region","rain","clipped","--bbox","60/30/0/31"),
         step("weekly","aggregate-temporal","clipped","weekly","--period","weekly"),
         step("totals","convert-to-totals","weekly","totals"),
         step("area","summarize-dim","totals","answer","--dim","latitude","--dim","longitude","--method","mean","--lat-weighted")],
        {"dates":("answer","@dates:time"),"totals_mm":("answer","precip"),"units":"mm"},
        [("weekly","totals"),("clip","area"),("totals","area")], ("deaccumulate",)))

    rates = np.array([[2+(d%4)+m*(1 if d<7 else 3)+((d+m)%3)*.4 for d in range(14)] for m in range(4)])
    weekly = np.array([[sum(row[w:w+7]) for w in (0,7)] for row in rates])
    spread = [math.sqrt(sum((x-float(np.mean(col)))**2 for x in col)/3) for col in weekly.T]
    result.append(Case("ensemble-flux-spread", "Ensemble uncertainty in weekly rainfall amounts",
        "flux.zarr contains four forecast members of precipitation flux in kg m-2 s-1 at daily end-of-interval leads 1–14. For liquid water, 1 kg m-2 equals 1 mm. Compute the sample standard deviation (ddof=1) across members of each member's total precipitation for leads (0,7] and (7,14] days. Return lead_days=[7,14], spread_mm, and units='mm'.",
        "Convert mass flux, total each member before calculating spread, and use sample rather than population standard deviation.",
        {"flux":dataset(rates/86400,("number","step"),{"number":range(4),"step":np.arange(1,15)*np.timedelta64(1,"D"),"time":np.datetime64("2024-01-01","ns")},units="kg m-2 s-1")},
        {"lead_days":[7,14],"spread_mm":spread,"units":"mm"},
        [step("units","unit-convert","flux","rates","--to-standard"),step("weekly","aggregate-temporal","rates","weekly","--period","weekly"),step("totals","convert-to-totals","weekly","totals"),step("spread","summarize-dim","totals","answer","--dim","number","--method","std")],
        {"lead_days":("answer","@days:step"),"spread_mm":("answer","precip"),"units":"mm"},
        [("units","totals"),("weekly","totals"),("totals","spread")],("deaccumulate",)))

    increments=np.array([[1+(d*m+d)%6 for d in range(14)] for m in (1,2,3)],dtype=float)
    accum=np.concatenate([np.zeros((3,1)),np.cumsum(increments,axis=1)],axis=1)
    med=[float(sorted(sum(row[w:w+7]) for row in increments)[1]) for w in (0,7)]
    result.append(Case("legacy-accumulation", "Recover rainfall totals from a legacy cumulative archive",
        "legacy.zarr holds cumulative-since-initialization precipitation amounts in mm for three members, including the zero baseline at lead 0. Derive nonnegative daily increments, then compute each member's totals for leads (0,7] and (7,14]. Return lead_days=[7,14], the member-median totals as median_mm, and units='mm'.",
        "Distinguish cumulative amounts from modern fetcher rates and preserve the forecast bucket boundaries.",
        {"legacy":dataset(accum,("number","step"),{"number":range(3),"step":np.arange(15)*np.timedelta64(1,"D"),"time":np.datetime64("2024-01-01","ns")},name="tp",units="mm").expand_dims(latitude=[0.],longitude=[30.])},
        {"lead_days":[7,14],"median_mm":med,"units":"mm"},
        [step("rates","deaccumulate","legacy","rates"),step("weekly","aggregate-temporal","rates","weekly","--period","weekly"),step("totals","convert-to-totals","weekly","totals"),step("median","summarize-dim","totals","answer","--dim","number","--method","median")],
        {"lead_days":("answer","@days:step"),"median_mm":("answer","tp"),"units":"mm"},[("rates","weekly"),("weekly","totals"),("totals","median")]))

    forecast=np.array([[280.,282.],[281.,284.],[285.,283.],[287.,288.]])
    obs=np.array([[1.,3.],[7.,9.],[8.,10.],[12.,11.],[13.,14.],[100.,100.]])
    # Valid forecasts Jan 2–5 pair with observation positions 1–4.
    errors=forecast-273.15-obs[1:5]
    result.append(Case("forecast-observation-bias", "Align a temperature forecast with observations",
        "forecast.zarr has t2m in K, scalar initialization 2024-01-01, and leads 1–4 days; obs.zarr has temperature in degree_Celsius from Jan 1–6. Match actual valid dates and grid coordinates, use only shared dates, and calculate forecast minus observation. Return dates, errors_c as [date][longitude] at latitude 0, bias_c as the mean error over dates for each longitude, and units='degree_Celsius'.",
        "Avoid lead/time broadcasting, handle Kelvin's offset, reconcile variable names, and inner-align dates.",
        {"forecast":dataset(forecast,("step","station_id"),{"step":np.arange(1,5)*np.timedelta64(1,"D"),"time":np.datetime64("2024-01-01","ns"),"station_id":[30.,31.]},name="t2m",units="K").rename(station_id="longitude").expand_dims(latitude=[0.]),"obs":dataset(obs,("time","station_id"),{"time":dates("2024-01-01",6),"station_id":[30.,31.]},name="temperature",units="degree_Celsius").rename(station_id="longitude").expand_dims(latitude=[0.])},
        {"dates":["2024-01-02","2024-01-03","2024-01-04","2024-01-05"],"errors_c":errors.tolist(),"bias_c":[sum(errors[:,j])/4 for j in range(2)],"units":"degree_Celsius"},
        [step("clock","step-to-time","forecast","clock"),step("units","unit-convert","clock","celsius","--to-standard"),step("names","rename","celsius","named","--to-name","temperature"),step("errors","difference","named obs","errors"),step("mean","summarize-dim","errors","answer","--dim","time","--method","mean")],
        {"dates":("errors","@dates:time"),"errors_c":("errors","temperature"),"bias_c":("answer","temperature"),"units":"degree_Celsius"},[("clock","errors"),("units","errors"),("names","errors"),("errors","mean")]))

    lats=[-10.,0.,10.]; lons=[50.,60.,70.,90.,100.,110.]
    base=np.array([[24+i*.5+j*.2 for j in range(6)] for i in range(3)])
    historical=np.array([base-2,base,base+2])
    anom=np.array([[[.5+t*.8+i*.4+j*.15 if j<3 else -.2-t*.3+i*.7+j*.05 for j in range(6)] for i in range(3)] for t in range(2)])
    w=[math.cos(math.radians(x)) for x in lats]
    west=[sum(a[i,j]*w[i] for i in range(3) for j in range(3))/(3*sum(w)) for a in anom]
    east=[sum(a[i,j]*w[i] for i in range(2) for j in range(3,6))/(3*sum(w[:2])) for a in anom]
    result.append(Case("iod-anomaly", "Build an SST baseline and calculate the Indian Ocean Dipole",
        "Build the arithmetic time-mean SST climatology from baseline.zarr. Subtract it from each target.zarr SST field (both degree_Celsius). Calculate cosine-latitude-weighted anomaly means over west 50–70E, 10S–10N and east 90–110E, 10S–0, including boundaries and equally weighting longitudes. Return dates, west_c, east_c, dmi_c=west-east, and units='degree_Celsius'.",
        "Compute anomalies before the index, broadcast a spatial baseline, and use different latitude extents for the dipole boxes.",
        {"baseline":dataset(historical,("time","latitude","longitude"),{"time":dates("2001-01-01",3),"latitude":lats,"longitude":lons},name="sst",units="degree_Celsius"),"target":dataset(base+anom,("time","latitude","longitude"),{"time":dates("2024-01-01",2),"latitude":lats,"longitude":lons},name="sst",units="degree_Celsius")},
        {"dates":["2024-01-01","2024-01-02"],"west_c":west,"east_c":east,"dmi_c":[a-b for a,b in zip(west,east)],"units":"degree_Celsius"},
        [step("baseline","summarize-dim","baseline","climo","--dim","time","--method","mean"),step("anomaly","difference","target climo","anomaly"),step("index","iod-mode-index","anomaly","answer","--variable","sst")],
        {"dates":("answer","@dates:time"),"west_c":("answer","west_indian_ocean_average_anomaly"),"east_c":("answer","east_indian_ocean_average_anomaly"),"dmi_c":("answer","iod_mode_index"),"units":"degree_Celsius"},[("baseline","anomaly"),("anomaly","index")]))

    models={"a":np.array([[12.,16.],[18.,22.]]),"b":np.array([[14.,18.],[24.,26.]]),"c":np.array([[20.,20.],[28.,30.]])}
    selected=np.array([m[1] for m in models.values()])
    result.append(Case("multimodel-disagreement", "Compare the same forecast week across three models",
        "Model stores a.zarr, b.zarr, c.zarr contain temperature for leads 7 and 14 days at stations A and B. b uses K; a and c use degree_Celsius. Select lead 14 days from each, normalize to Celsius, and combine in model order a,b,c. Return model_values_c as [model][station], sample inter-model standard deviation spread_c per station (ddof=1), and units='degree_Celsius'.",
        "Select matching leads, remove scalar lead coordinates, normalize units before combining, and summarize the model axis.",
        {k:dataset(v+(273.15 if k=="b" else 0),("step","station_id"),{"step":np.array([7,14])*np.timedelta64(1,"D"),"station_id":["A","B"],"time":np.datetime64("2024-01-01","ns")},name="temperature",units="K" if k=="b" else "degree_Celsius") for k,v in models.items()},
        {"model_values_c":selected.tolist(),"spread_c":[math.sqrt(sum((x-sum(col)/3)**2 for x in col)/2) for col in selected.T],"units":"degree_Celsius"},
        [step("a","select","a","a14","--dim","step","--value","14D"),step("b","select","b","b14","--dim","step","--value","14D"),step("c","select","c","c14","--dim","step","--value","14D"),step("units","unit-convert","b14","bc","--to-standard"),step("combine","concat","a14 bc c14","combined","--dim","model","--coords","a,b,c"),step("spread","summarize-dim","combined","answer","--dim","model","--method","std")],
        {"model_values_c":("combined","temperature"),"spread_c":("answer","temperature"),"units":"degree_Celsius"},[("a","combine"),("b","combine"),("c","combine"),("units","combine"),("combine","spread")]))

    rain=np.array([2.,1.,4.,0.,3.,5.,8.,2.,6.,1.,4.,7.,0.,9.])
    result.append(Case("rolling-nonoverlap", "Export two independent totals from rolling rainfall windows",
        "From daily rain.zarr, construct left-labeled 7-day rolling mean rates. Export only windows starting 2024-01-01 and 2024-01-08 as precipitation totals; these windows do not overlap. Require seven samples for a valid window. Return dates, totals_mm, and units='mm'.",
        "Rolling windows overlap by default; select disjoint windows before converting mean rates to totals.",
        {"rain":dataset(rain,("time",),{"time":dates("2024-01-01",14)})},
        {"dates":["2024-01-01","2024-01-08"],"totals_mm":[sum(rain[:7]),sum(rain[7:])],"units":"mm"},
        [step("rolling","aggregate-temporal","rain","rolling","--window","7"),step("select","select","rolling","selected","--dim","time","--index","0","--index","7"),step("totals","convert-to-totals","selected","answer")],
        {"dates":("answer","@dates:time"),"totals_mm":("answer","precip"),"units":"mm"},[("rolling","select"),("select","totals")],("deaccumulate",)))

    mt=[cftime.DatetimeNoLeap(2000,2,27),cftime.DatetimeNoLeap(2000,2,28),cftime.DatetimeNoLeap(2000,3,1),cftime.DatetimeNoLeap(2000,3,2)]
    mv=np.array([280.,283.,286.,285.]); ov=np.array([6.,8.,99.,11.,10.])
    err=[mv[i]-273.15-ov[j] for i,j in enumerate([0,1,3,4])]
    result.append(Case("calendar-alignment", "Verify a no-leap model across February 29",
        "model.zarr is a noleap-calendar temperature series in K; obs.zarr uses Gregorian dates and Celsius, including February 29, 2000. Preserve month/day when converting the model to the standard calendar. Compare only shared dates (do not fill or interpolate Feb 29). Return dates, model-minus-observation errors_c, mean_bias_c, and units='degree_Celsius'.",
        "Align calendars and units without shifting March values or including the unpaired leap day.",
        {"model":dataset(mv,("time",),{"time":mt},name="temperature",units="K"),"obs":dataset(ov,("time",),{"time":dates("2000-02-27",5)},name="temperature",units="degree_Celsius")},
        {"dates":["2000-02-27","2000-02-28","2000-03-01","2000-03-02"],"errors_c":err,"mean_bias_c":sum(err)/4,"units":"degree_Celsius"},
        [step("calendar","convert-calendar","model","standard","--calendar","standard"),step("units","unit-convert","standard","celsius","--to-standard"),step("errors","difference","celsius obs","errors"),step("mean","summarize-dim","errors","answer","--dim","time","--method","mean")],
        {"dates":("errors","@dates:time"),"errors_c":("errors","temperature"),"mean_bias_c":("answer","temperature"),"units":"degree_Celsius"},[("calendar","errors"),("units","errors"),("errors","mean")]))

    grid=np.array([[i*i+2*j*j for j in range(5)] for i in range(5)],dtype=float)
    interpolated=np.array([[sum(grid[i+di,j+dj] for di in (0,1) for dj in (0,1))/4 for j in (0,2)] for i in (0,2)])
    truth=np.array([[2.,10.],[7.,20.]])
    error=interpolated-truth
    result.append(Case("grid-alignment", "Align two temperature grids before measuring their difference",
        "fine.zarr contains a temperature field on integer-degree coordinates 0 through 4. Interpolate it bilinearly onto ref.zarr's grid (latitude and longitude 0.5,2.5; spacing 2 degrees; offset 0.5). Compute interpolated fine minus reference. Return latitude, longitude, errors_c as [latitude][longitude], unweighted spatial mean_bias_c, and units='degree_Celsius'.",
        "Grid alignment requires interpolation at target points, not block averaging or accidental empty-coordinate subtraction.",
        {"fine":dataset(grid,("latitude","longitude"),{"latitude":np.arange(5.),"longitude":np.arange(5.)},name="temperature",units="degree_Celsius",interval=None),"ref":dataset(truth,("latitude","longitude"),{"latitude":[.5,2.5],"longitude":[.5,2.5]},name="temperature",units="degree_Celsius",interval=None)},
        {"latitude":[.5,2.5],"longitude":[.5,2.5],"errors_c":error.tolist(),"mean_bias_c":float(sum(error.flat)/4),"units":"degree_Celsius"},
        [step("grid","coarsen","fine","aligned","--target-resolution","2","--offset","0.5"),step("errors","difference","aligned ref","errors"),step("mean","summarize-dim","errors","answer","--dim","latitude","--dim","longitude","--method","mean")],
        {"latitude":("errors","latitude"),"longitude":("errors","longitude"),"errors_c":("errors","temperature"),"mean_bias_c":("answer","temperature"),"units":"degree_Celsius"},[("grid","errors"),("errors","mean")]))

    starts=[0,1,6,7,9]; ends=[1,6,7,9,14]; values=[2.,6.,10.,4.,8.]
    ds=dataset(values,("time",),{"time":np.datetime64("2024-01-01","ns")+np.array(starts)*np.timedelta64(1,"D")},interval=None)
    ds["time_bounds"] = (("time","bounds"),np.datetime64("2024-01-01","ns")+np.array(list(zip(starts,ends)))*np.timedelta64(1,"D"))
    ds.time.attrs["bounds"]="time_bounds"
    result.append(Case("duration-weighted-rainfall", "Integrate irregular precipitation intervals",
        "irregular.zarr has precipitation rates and explicit time_bounds. Each rate is constant over its half-open [start,end) interval; intervals have unequal durations. Compute complete weekly totals for Jan 1–8 and Jan 8–15, weighting rates by covered duration. Return dates (week starts), totals_mm, and units='mm'.",
        "An arithmetic mean of records is wrong when each record represents a different number of days.",
        {"irregular":ds},{"dates":["2024-01-01","2024-01-08"],"totals_mm":[42.,48.],"units":"mm"},
        [step("weighted","aggregate-temporal","irregular","weekly","--period","weekly"),step("totals","convert-to-totals","weekly","answer","--variable","precip")],
        {"dates":("answer","@dates:time"),"totals_mm":("answer","precip"),"units":"mm"},[("weighted","totals")],("deaccumulate",)))
    from .e2e_cases import e2e_cases
    from .refined import case as refined_case
    return result + e2e_cases() + ([refined_case()] if include_refined else [])


def write_inputs(case, destination):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    for name,ds in case.datasets.items():
        ds.to_zarr(destination/f"{name}.zarr",mode="w",zarr_format=2,consolidated=True)


def extract(case, workspace):
    answer={}
    for key,spec in case.exports.items():
        if isinstance(spec,str):
            answer[key]=spec
            continue
        store,field=spec
        with xr.open_zarr(Path(workspace)/f"{store}.zarr",chunks=None) as ds:
            if field.startswith("@dates:"):
                answer[key]=[str(x)[:10] for x in ds[field.split(":")[1]].values]
            elif field.startswith("@days:"):
                answer[key]=(ds[field.split(":")[1]].values/np.timedelta64(1,"D")).tolist()
            else:
                answer[key]=ds[field].values.squeeze().tolist()
    return answer
