from database import init_db, db_session
from flask import Flask
from models import *
import json
from elasticsearch import Elasticsearch
from flask.ext.cache import Cache
import redis
init_db()

app = Flask(__name__)


es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

cache = Cache(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_KEY_PREFIX': 'redfcache',
    'CACHE_REDIS_HOST': '127.0.0.1',
    'CACHE_REDIS_PORT': '6379',
    'CACHE_REDIS_URL': 'redis://127.0.0.1:6379'
    })
@app.route('/alldoctors')
def get_all_doctors():
    doctor_data = {}
    doclist=[]
    for d in Doctor.query.all():
    	print d.name
    	doctor_data = {}
    	clinicList = []
    	doctor_data['name'] = d.name
    	doctor_data['id'] = d.id
    	doctor_data['email'] = d.email
    	doctor_data['recommendations']=d.recommendations
    	doctor_data['photo']=d.photo
        doctor_data['location'] =Locality.query.get(d.locality).name
    	for clinic in d.clinics:
    		clinicMap={}
	    	clinicMap["name"] = clinic.name
	    	clinicMap["address"] = clinic.address
	    	clinicMap["fees"] = assoc_doc_clinic.query.filter(\
                assoc_doc_clinic.doc_id == d.id,assoc_doc_clinic.clinic_id == \
                clinic.id).first().fees
	    	clinicList.append(clinicMap)
    	doctor_data["clinics"] = clinicList
    	doctor_data['specialities'] = [speciality.name for speciality in d.specialities]
    	doclist.append(doctor_data)
    response= {'data': doclist, 'success':True}
    return json.dumps(response)




@app.route('/doctor/<doc_id>')
@cache.memoize(timeout=5000)
def get_doctor_profile(doc_id):
    d=Doctor.query.get(doc_id)
    if not d.published:
        return json.dumps({'success':False,'Error':'No such Doctor exists\
            (or is published)'})
    doctor = {}
    doctor['name'] = d.name
    doctor['id'] = d.id
    doctor['email'] = d.email
    doctor['recommendations'] = d.recommendations
    doctor['experience'] = d.experience
    doctor['qualification']=d.qualification
    doctor['locality'] = Locality.query.get(d.locality).name
    doctor['city'] = City.query.get(Locality.query.get(d.locality).city_id).name
    doctor['photo'] = d.photo
    doctor['salutation'] = d.salutation
    clinicLists =[]
    for clinic in d.clinics:
        clinicmap = {}
        clinicmap['name'] = clinic.name
        clinicmap['address'] = clinic.address
        clinicmap['fees'] = assoc_doc_clinic.query.filter(assoc_doc_clinic.doc_id==d.id,
                    assoc_doc_clinic.clinic_id == clinic.id).first().fees
        clinicmap['timing'] = assoc_doc_clinic.query.filter(assoc_doc_clinic.doc_id==d.id,
                    assoc_doc_clinic.clinic_id == clinic.id).first().timings
        clinicLists.append(clinicmap)
    doctor['clinics'] = clinicLists
    doctor['specialities'] = [{"name":spec.name} for spec in d.specialities]
    response= {'data': doctor, 'success':True}
    '''
    for k,v in d.__dict__.iteritems():
      if(k[0]!='_'):
        doctor[k]=v
    response= {'data': d.serialize(), 'success':True}'''
    return json.dumps(response)
    #return json.dumps(d.__dict__)




@app.route('/allclinics')
def get_all_clinics():
    clinicList = []
    for c in Clinic.query.all():
        clinicmap = {}
        clinicmap['name'] = c.name
        clinicmap['address'] = c.address
        clinicmap['id'] = c.id
        #clinicmap['city'] = City.query.get(c.city).name
        clinicList.append(clinicmap)
    response = {'clinics': clinicList,'success':True}
    return json.dumps(response)

#----------------------------------------------------------------ElasticSearch--------------------------------------------------------------

@app.route('/location/<city>/<location_term>')
def locationsearch(city,location_term):
    '''
    This function is used for (Elastic) searching the hits for a location.
    '''
    res=es.search(index="practo_index", doc_type = "location",
            body={  "query":{
                "filtered":{
                    "query":{
                        "query_string": {
                             "default_field": "name",
                             "query": location_term
                          }
                    },
                    "filter":{
                        "term": {"city": city.lower()}
                    }
                }      
           }
        })
    locality_list = []                                                   
    for loc in res['hits']['hits']:
        print loc
        locality_list.append({"name":loc['_source']['name'],"type":"Locality"})
    response = {}
    response={"total":res['hits']['total'],"matches":locality_list}
    return json.dumps(response)

@app.route('/query/<city>/<query_term>')
def homequery(city,query_term):
    '''
    This function is used for Elastic search of query, which can be the name 
        of a doctor , clinic, or speciality.      '''

    res=es.search(index="practo_index", 
   
  body={  "query":{
                "filtered":{
                    "query":{
                        "query_string": {   
                            "query":query_term
                        }
                    },
                    "filter":{
                        "or":[{
                                "term": {"city": city.lower()}
                            },
                            {
                                "term":{"_type":"specialities"}
                            }
                        ]
                    }
                }      
           }
        })
    hitlist=[]
    print res
    for hit in res['hits']['hits']:

        if hit['_type']=="doctors":
            hitlist.append({"name":hit['_source']['name'], "type" : "doctor"})

        if hit['_type']=="clinics":
            hitlist.append({"name":hit['_source']['name'],"type" : "clinic"})

        if hit['_type']=="specialities":
            hitlist.append({"name":hit['_source']['name'],"type" : \
                "specialities"})
    response = {"total":res['hits']['total'],"matches" : hitlist}
    return json.dumps(response)

#---------------------------------------------------------------------Querying---------------------------------------------------------------

@app.route('/<city_term>/<query_term>')
@cache.memoize(timeout=5000)
def SearchSpecLocation(city_term,query_term):
    try:
        searchedSpecId=Speciality.query.filter(Speciality.name == \
        query_term).first().id 
    except:
        return json.dumps({"success":False,
         "results":"Speciality Not found. <a href = './../../'>Go back</a>"})
    try:
        searched_City_Id = City.query.filter(City.name ==city_term).first().id
    except:
        return "No city like %s found"%city_term
    
    list_of_doc_specs = doc_spec.query.filter(doc_spec.spec_id == searchedSpecId).all()

    list_of_potential_doc_ids = [l.doc_id for l in list_of_doc_specs]

    list_of_doc_queries = Doctor.query.filter(Doctor.id.in_(list_of_potential_doc_ids))
    #        .filter(Locality.query.get(Doctor.locality).city_id == searched_City_Id )

    list_of_final_docs=[]
    for d in list_of_doc_queries:
        if Locality.query.get(d.locality).city_id == searched_City_Id:
            list_of_final_docs.append(d)


    list_of_doc_ids=[]
    for l in list_of_final_docs:
        list_of_doc_ids.append({"id" : str(l.id), 
            "name" : str(l.name), "photo" : str(l.photo), 
            "qualification":str(l.qualification),
            "recommendations":str(l.recommendations),
            "salutation":str(l.salutation),
            "locality": Locality.query.get(l.locality).name,
            "experience" : str(l.experience)})
    return json.dumps({"results":list_of_doc_ids,"success":True})

#-----------------------------------------------------------------------End of Views----------------------------------------------------------


if __name__ == '__main__':
	app.secret_key = 'super secret35796Shreysfjkhogh08923epuoij'
	app.run(host = 'localhost',port = 8000,debug=True)