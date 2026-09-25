import os
import requests

TRAVELPAYOUTS_API_TOKEN = os.environ.get("TRAVELPAYOUTS_API_TOKEN", "")
TRAVELPAYOUTS_MARKER = os.environ.get("TRAVELPAYOUTS_MARKER", "")

def fetch_cheap_flights(origin, destination, depart_date, return_date=None, currency="USD"):
    url = "https://api.travelpayouts.com/v1/prices/cheap"
    
    headers = {
        "X-Access-Token": TRAVELPAYOUTS_API_TOKEN,
        "Accept-Encoding": "gzip,deflate"
    }
    
    params = {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "depart_date": depart_date,
        "currency": currency.lower()
    }
    
    if return_date:
        params["return_date"] = return_date

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        flights = []
        dest_data = data.get("data", {}).get(destination.upper(), {})
        
        for key, item in dest_data.items():
            flights.append({
                "flight_number": item.get("flight_number"),
                "airline": item.get("airline"),
                "price": item.get("price"),
                "departure_at": item.get("departure_at"),
                "return_at": item.get("return_at"),
                "transfers": item.get("transfers", 0),
                "redirect_url": f"/api/redirect?origin={origin}&destination={destination}&partner={item.get('airline')}&price={item.get('price')}"
            })
            
        return {"success": True, "data": flights}
        
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "data": []}