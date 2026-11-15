# Connect your personal Outlook calendar

Bej uses a desktop public-client registration and Microsoft sign-in. Do not create a client secret or paste passwords/tokens into chat.

## Prepare the registration

1. Open [Microsoft Entra](https://entra.microsoft.com/), then **App registrations → New registration**.
2. Name it **Bej Secretary** and choose **Personal Microsoft accounts only**, or the option that also includes personal accounts if personal-only is unavailable.
3. After registering, copy the **Application (client) ID**. This identifier is not a secret.
4. In **Authentication**, enable **Allow public client flows** for the device-code sign-in used by Bej.
5. Under **API permissions**, add Microsoft Graph **Delegated** permission `Calendars.ReadWrite`. Do not add application permissions or create a client secret.

Microsoft's registration documentation lists an Azure account/subscription, an Entra tenant, and an appropriate registration role as prerequisites. If the portal says you have no directory or cannot register applications, report that exact obstacle; do not purchase a subscription just to continue. [Official registration instructions](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app)

## In Bej

Enter the client ID in Connections, then start sign-in. Open the displayed Microsoft verification URL, enter the code, choose your personal account, and review consent. Bej stores its token cache in Windows credential storage. The app will not receive your Microsoft password. Device-code authentication is provided by [MSAL Python](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens).

The calendar grant can technically cover your account's calendars; Bej restricts task writes to its selected **Bej** calendar and requires approval of displayed task blocks. Creating that calendar and event writes use [delegated Calendars.ReadWrite](https://learn.microsoft.com/en-us/graph/api/user-post-calendars?view=graph-rest-1.0).

Preview each batch before publishing. Only the displayed title and times are sent; source notes are not uploaded. Offline operation uses a clearly dated cache and never claims a write succeeded without confirmation from Microsoft.

## Verified on this laptop

The client ID is configured privately, the user completed Microsoft sign-in, and Bej created/reused its separate calendar and synchronized an empty day successfully. The saved sign-in also survived restart. No task events were published during verification. Use the in-app publication preview to approve actual task blocks.

Entra ID Free has no product charges, and standard calendar Graph calls are not additional metered API usage within normal limits. No Azure-hosted server or paid Entra license is needed for this local app. Other separately created Azure resources or premium products can still create charges. [Entra billing](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/microsoft-entra-id-free), [Graph costs](https://learn.microsoft.com/en-us/graph/metered-api-overview).
