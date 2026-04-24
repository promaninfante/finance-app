/**
 * Google Apps Script — Drive inbox poller for finance-app ingest Lambda.
 *
 * SETUP (one-time):
 *   1. Open https://script.google.com, create a new project.
 *   2. Paste this entire file into the editor.
 *   3. Project Settings → Script Properties → add the five keys below.
 *   4. Triggers → Add Trigger → checkInbox, Time-driven, Every 5 minutes.
 *   5. Authorise the script when prompted (needs Drive read + UrlFetch).
 *
 * Required Script Properties (Project Settings → Script Properties):
 *   LAMBDA_URL        — Function URL from `sam deploy` Outputs.IngestFunctionUrl
 *   INGEST_SECRET     — Value of SSM /finance/ingest_shared_secret
 *   INBOX_FOLDER_ID   — Google Drive folder ID (last segment of the folder URL)
 *   SUPABASE_USER_ID  — Your Supabase auth.users.id (UUID)
 *   ACCOUNT_ID        — UUID of your accounts row in Supabase
 */

function checkInbox() {
  var props  = PropertiesService.getScriptProperties().getProperties();
  var seen   = PropertiesService.getUserProperties();

  var folder = DriveApp.getFolderById(props['INBOX_FOLDER_ID']);
  var files  = folder.getFiles();

  while (files.hasNext()) {
    var file   = files.next();
    var fileId = file.getId();

    // Skip files already sent to the Lambda.
    if (seen.getProperty('seen_' + fileId)) {
      continue;
    }

    var payload = JSON.stringify({
      user_id:       props['SUPABASE_USER_ID'],
      account_id:    props['ACCOUNT_ID'],
      drive_file_id: fileId,
      filename:      file.getName()
    });

    var options = {
      method:           'post',
      contentType:      'application/json',
      payload:          payload,
      headers:          { 'x-ingest-secret': props['INGEST_SECRET'] },
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(props['LAMBDA_URL'], options);
    var code     = response.getResponseCode();
    var body     = response.getContentText();

    Logger.log('File %s → HTTP %s: %s', fileId, code, body);

    // Mark seen regardless of Lambda response to avoid infinite retries.
    // A failed statement gets status='error' in Supabase for investigation.
    seen.setProperty('seen_' + fileId, new Date().toISOString());
  }
}

/**
 * Run once manually to verify the Lambda URL and secret are correct
 * before relying on the time-based trigger.
 */
function testConnection() {
  var props = PropertiesService.getScriptProperties().getProperties();
  var options = {
    method:           'post',
    contentType:      'application/json',
    payload:          '{}',
    headers:          { 'x-ingest-secret': props['INGEST_SECRET'] },
    muteHttpExceptions: true
  };
  var response = UrlFetchApp.fetch(props['LAMBDA_URL'], options);
  Logger.log('Status: %s, Body: %s', response.getResponseCode(), response.getContentText());
}
