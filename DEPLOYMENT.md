# Publish the app online

The app is designed for Streamlit Community Cloud. The repository includes client-provided GIS data whose reuse terms are not yet documented, so keep the GitHub repository private and make only the Streamlit app public. A public app still exposes the map and scenario results it renders.

## Prepare and deploy

1. Push the reviewed deployment branch to the existing GitHub repository. Do not merge it into `main` as part of deployment.
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) with the GitHub account that has admin access to the repository. Grant Streamlit access only to this repository if GitHub offers that choice.
3. Choose **Create app** and select the repository, deployment branch, and `app.py` as the app file.
4. In **Advanced settings**, choose Python **3.11**, matching the local development runtime.
5. Deploy. Once it starts, open the app settings and set its visibility to public so groupmates and the client can open the URL without signing in.
6. Copy the resulting `https://<name>.streamlit.app` address and share it with the intended audience.

No app secrets or API keys are currently required. The basemap uses OpenStreetMap tiles and therefore needs internet access in the viewer's browser.

## Updates and hosting limits

The deployed app follows its selected GitHub branch. Pushing a change to that branch triggers an app update. Do development locally and push only reviewed changes to the deployment branch.

Community Cloud can put an app to sleep after 12 hours without traffic. A viewer can wake it by opening the link and choosing the wake option. This is suitable for a presentation prototype, but does not guarantee uninterrupted service.

The current `requirements.txt` pins the versions installed in the local Python 3.11 environment. Update those pins deliberately when the app dependencies are changed.
