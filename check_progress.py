import json
data = json.load(open(r"c:\Users\wang\Projects\H100_package_realeval\.upload_state.json"))
done = data["done"]
print(f"Progress: {len(done)} files")
print(f"Last 5: {done[-5:]}")
