# Stripe Paywall Setup

This paywall is a cost-control gate for the portfolio demo. It sells one-time audit credit packs and supports private invite codes. It does not use subscriptions, accounts, or a client-side Stripe SDK.

## What You Need

- A Stripe account.
- An Azure Storage connection string for the billing credit ledger.
- A deployed app URL, for example `https://youtube-ad-compliance-checker-srikara.azurewebsites.net`.
- App Service application settings for the secrets below.

## Stripe Dashboard Steps

1. Create or sign in to a Stripe account at `https://dashboard.stripe.com`.
2. Start in **Test mode** first.
3. Open **Developers > API keys**.
4. Copy the **Secret key**:
   - Test key starts with `sk_test_`.
   - Live key starts with `sk_live_`.
   - This app only needs the secret key because Checkout sessions are created by the backend.
5. Open **Developers > Webhooks**.
6. Add an endpoint:

```text
https://<your-webapp-name>.azurewebsites.net/billing/webhook
```

7. Select this event:

```text
checkout.session.completed
```

8. Copy the endpoint **Signing secret**. It starts with `whsec_`.

## Azure App Service Settings

Set these in Azure Portal under **App Service > Environment variables** or with `az webapp config appsettings set`.

```text
PAYWALL_ENABLED=true
PUBLIC_SITE_URL=https://<your-webapp-name>.azurewebsites.net
BILLING_TOKEN_SECRET=<long-random-secret>
STRIPE_SECRET_KEY=<sk_test_or_sk_live_value>
STRIPE_WEBHOOK_SECRET=<whsec_value>
AZURE_STORAGE_CONNECTION_STRING=<your-storage-connection-string>
PAYWALL_CREDIT_PACK_CENTS=300
PAYWALL_CREDIT_PACK_CREDITS=3
MAX_AUDIT_VIDEO_SECONDS=180
BILLING_INVITE_CODES_JSON={"RECRUITER-DEMO":{"credits":3,"max_redemptions":20}}
```

Generate `BILLING_TOKEN_SECRET` yourself. It should be a long random string and should not be committed to the repo.

Example PowerShell generator:

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```

## Test Payment

In Stripe Test mode, buy credits through the deployed app and use Stripe's test card:

```text
4242 4242 4242 4242
```

Use any future expiry date, any three-digit CVC, and any ZIP/postcode.

After checkout succeeds:

- Stripe redirects back to `PUBLIC_SITE_URL`.
- The frontend claims the Checkout session.
- The backend verifies Stripe payment status.
- Credits are added to the browser's email-scoped access token.

The webhook also grants credits idempotently, so duplicate webhook deliveries should not double-credit the user.

## Going Live

When you are ready to accept real payments:

1. Activate your Stripe account for live payments.
2. Switch out of Test mode in the Stripe Dashboard.
3. Replace `STRIPE_SECRET_KEY` with the live `sk_live_...` key.
4. Create or update the live webhook endpoint.
5. Replace `STRIPE_WEBHOOK_SECRET` with the live endpoint `whsec_...` secret.
6. Restart the App Service after changing settings.

Keep test and live values separate. Test-mode objects and live-mode objects are different in Stripe.

