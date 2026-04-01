rm -rf .venv
python3 -m venv .venv



# Move to your project directory
cd ~/ProjectStage/backend_pipeline

# Activate the virtual environment
source .venv/bin/activate


# 1. Kill everything related to the project
docker-compose down --volumes --remove-orphans

# 2. Prune Docker networks (solves the "Network projectstage_default Creating" hang)
docker network prune -f

# 3. Clean up any stuck volumes manually just in case
docker volume rm $(docker volume ls -q | grep esdata) 2>/dev/null

# 4. Start the services again
docker-compose up -d



#and to check if the es is started 
# This will repeat until it gets a response or you hit Ctrl+C
until curl -s localhost:9200; do 
  echo "⏳ Waiting for Elasticsearch to wake up..."
  sleep 5
done
echo "✅ Elasticsearch is LIVE!"




then 

pip install -r requirements.txt

python3 parser.py
python3 main.py
uvicorn BlacklistCkeck:app 

to reset the es 
# First, tell ES to allow wildcard deletions
curl -X PUT "localhost:9200/_cluster/settings" -H 'Content-Type: application/json' -d'
{
  "persistent": {
    "action.destructive_requires_name": false
  }
}'

# Now the wildcard delete will work
curl -X DELETE "localhost:9200/mail-journeys-sent-2026-01-28"
curl -X DELETE "localhost:9200/mail-journeys-sent-2026-01*"
curl -X DELETE "localhost:9200/mail-journeys-received-2026-01*"
curl "localhost:9200/_cat/indices?v&h=index,docs.count,store.size"
python3 parser.py

curl -X DELETE "localhost:9200/dnsbl-checks"

to know details 

curl "localhost:9200/_cat/indices?v&h=index,docs.count,store.size"


#bsh tkhadmo ba3d l setup

cd ~/ProjectStage/backend_pipeline
source .venv/bin/activate

export DATABASE_URL="postgresql://cg_user:cg_password@localhost:5432/cg_logs"




http://localhost:9200/mail-journeys-sent-2026-01-27/_search?size=50&pretty
http://localhost:9200/mail-journeys-received-2026-01-27/_search?size=50&pretty
http://localhost:9200/mail-journeys-*/_search?q=qid:12345ABCDE&pretty








# Move to your project directory
cd ~/ProjectStage/backend_pipeline

# Activate the virtual environment
source .venv/bin/activate
docker-compose up -d


cd logs_filter_frontend_elastic
npm start









ki tamel l setup awl mara paste this
curl -X PUT "http://localhost:9200/mail-logs" -H 'Content-Type: application/json' -d'
{
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "qid": { "type": "keyword" },
      "delivery_id": { "type": "keyword" },
      "sender": { "type": "keyword" },
      "recipient": { "type": "keyword" },
      "log_type": { "type": "keyword" },
      "source_server": { "type": "keyword" }
    }
  }
}'
w ba3d this
curl -X PUT "http://localhost:9200/_ingest/pipeline/cg-mail-logs-pipeline" \
     -H "Content-Type: application/json" \
     -d @pipeline.json

to check ken tekhdem do this 
curl -X GET "http://localhost:9200/_ingest/pipeline/cg-mail-logs-pipeline?pretty"