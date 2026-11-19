import json #used for JSON libray 


from dataclasses import asdict, dataclass #used to load dataclassses library
#dataclass is used to turn a plain class into a struct
#asdict is used to turn the filled struct back into the dictionary



@dataclass #takes the DataStatic class below and auto generates "__init__" so it can be filled in like a struct
class DataStatic: #used to define a struct whith the data format (float for decimals)
    xdot_ms: float
    ydot_ms: float
    salinity_ppt: float
    temperature_c: float

    #json.dumps turns Python data into a text string
    def to_json(self) -> str: #retuns text or the ROS String message and method for every filled struct
        return json.dumps({"env_data_static": asdict(self)})
        #asdict -> dict, put it inside a "env_data_static" key, json.dumps -> text string