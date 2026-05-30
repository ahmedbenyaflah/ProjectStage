// SMTP error codes for support: what they mean and suggested actions
// Used in telecom / agency SMTP flow logs for anomaly detection
export const SMTP_ERROR_EXPLANATIONS = {

  // ── 4xx Transient failures ──────────────────────────────────────────────
  420: {
    title: 'Timeout — service temporarily unavailable',
    meaning: 'The receiving server did not respond in time. Connection timed out before the transaction completed.',
    action: 'Retry. If persistent, check network path between your relay and the destination server.',
  },
  421: {
    title: 'Service not available',
    meaning: 'The receiving server is temporarily refusing connections (e.g. overloaded or in maintenance). The transmission channel was closed.',
    action: 'Retry later. If it persists, check recipient server status or contact their postmaster.',
  },
  431: {
    title: 'Receiving server low on disk space',
    meaning: 'The destination server has insufficient disk space to store additional messages at this time.',
    action: 'Retry later. Recipient admin should free disk space or expand storage.',
  },
  432: {
    title: 'Recipient\'s Exchange server unavailable',
    meaning: 'Delivery to the recipient\'s Exchange server failed because it is not reachable or accepting mail.',
    action: 'Check connectivity to the recipient mail server. Retry after a short interval.',
  },
  441: {
    title: 'Recipient\'s server not responding',
    meaning: 'The remote server is reachable but is not responding to SMTP commands.',
    action: 'Retry later. If repeated, the recipient\'s mail infrastructure may be degraded.',
  },
  442: {
    title: 'Connection dropped during transmission',
    meaning: 'The connection to the receiving server was unexpectedly closed mid-session.',
    action: 'Retry. Investigate firewall or TLS negotiation issues if this recurs.',
  },
  446: {
    title: 'Maximum hop count exceeded',
    meaning: 'The message has been relayed through too many servers. A routing loop is likely.',
    action: 'Inspect relay and routing configuration for loops. Check MX records.',
  },
  447: {
    title: 'Message timed out during delivery',
    meaning: 'The message stayed too long in the queue waiting for a successful delivery attempt.',
    action: 'Check whether the destination server is reachable. Review queue expiry settings.',
  },
  449: {
    title: 'Routing error',
    meaning: 'A routing failure prevented the message from being forwarded to the next hop.',
    action: 'Verify MX and relay routing tables. Check DNS resolution for the destination domain.',
  },
  450: {
    title: 'Mailbox unavailable',
    meaning: 'The recipient mailbox exists but could not be reached (e.g. busy or locked).',
    action: 'Retry after a short delay. For clients: confirm the mailbox is not full or restricted.',
  },
  451: {
    title: 'Local error in processing',
    meaning: 'The receiving server aborted the action due to a local processing error (e.g. disk or config issue).',
    action: 'Retry. If repeated, the recipient side needs to check their server logs and storage.',
  },
  452: {
    title: 'Insufficient system storage',
    meaning: 'The receiving server ran out of disk space or resources and could not accept the message.',
    action: 'Retry later. Recipient should free space or scale capacity.',
  },
  454: {
    title: 'TLS not available',
    meaning: 'The server was unable to start TLS negotiation. The secure channel could not be established.',
    action: 'Check TLS certificate validity and server TLS configuration on both sides.',
  },

  // ── 5xx Permanent failures ──────────────────────────────────────────────
  500: {
    title: 'Syntax error — command unrecognized',
    meaning: 'The server could not parse the SMTP command sent by the client. The command is malformed or unsupported.',
    action: 'Check the SMTP session commands. This may indicate a buggy client or protocol mismatch.',
  },
  501: {
    title: 'Syntax error in parameters or arguments',
    meaning: 'The SMTP command was recognized but its parameters or arguments have an invalid syntax.',
    action: 'Verify the MAIL FROM / RCPT TO address format and any extended SMTP parameters.',
  },
  502: {
    title: 'Command not implemented',
    meaning: 'The SMTP command sent is valid but is not supported by the receiving server.',
    action: 'Verify EHLO capability negotiation. Avoid using unsupported SMTP extensions.',
  },
  503: {
    title: 'Bad sequence of commands',
    meaning: 'The SMTP commands were sent in the wrong order (e.g. RCPT TO before MAIL FROM).',
    action: 'Review the SMTP handshake flow. Ensure commands follow the correct sequence.',
  },
  504: {
    title: 'Command parameter not implemented',
    meaning: 'A parameter used with an SMTP command is not supported by the receiving server.',
    action: 'Check EHLO capabilities and remove unsupported options from the command.',
  },
  510: {
    title: 'Bad email address',
    meaning: 'The recipient address is syntactically invalid and cannot be delivered to.',
    action: 'Correct the address format and verify with the sender.',
  },
  511: {
    title: 'Bad email address (destination)',
    meaning: 'The destination address does not exist or cannot be found on the receiving server.',
    action: 'Verify the recipient address. Check for typos or deprovisioned accounts.',
  },
  512: {
    title: 'Domain not found',
    meaning: 'DNS lookup for the destination domain failed. The domain has no MX or A record.',
    action: 'Verify DNS records for the recipient domain. Check with the domain owner.',
  },
  521: {
    title: 'Domain does not accept mail',
    meaning: 'The destination domain is configured to refuse all incoming mail.',
    action: 'Confirm the correct domain. This is often a misconfigured or parked domain.',
  },
  523: {
    title: 'Message size exceeds recipient storage limit',
    meaning: 'The recipient\'s mailbox quota or the server\'s size limit would be exceeded by this message.',
    action: 'Reduce attachment size or ask the recipient to free up mailbox space.',
  },
  530: {
    title: 'Authentication required',
    meaning: 'The server requires SMTP authentication before accepting mail, but the client did not authenticate.',
    action: 'Configure SMTP AUTH credentials in the sending mail client or relay.',
  },
  535: {
    title: 'Authentication credentials invalid',
    meaning: 'SMTP authentication failed. The username/password combination was rejected by the server.',
    action: 'Verify credentials. Reset the password if needed and update all relay configurations.',
  },
  541: {
    title: 'Message rejected — access denied',
    meaning: 'The receiving server refused the message due to content policy, reputation filtering, or explicit block.',
    action: 'Review message content for spam indicators. Check if the sending IP is blacklisted.',
  },
  550: {
    title: 'Mailbox unavailable / User not found',
    meaning: 'The mailbox does not exist, is disabled, or the server rejected delivery (e.g. policy or invalid address).',
    action: 'Verify the recipient address with the client. Check for typos or deprovisioned mailboxes.',
  },
  551: {
    title: 'User not local',
    meaning: 'The recipient is not local to this server; the sender should try a different forwarding path.',
    action: 'Confirm routing and MX records for the destination domain.',
  },
  552: {
    title: 'Exceeded storage allocation',
    meaning: 'The recipient mailbox has exceeded its quota and cannot accept more mail.',
    action: 'Ask the client to free space or increase quota. Inform end user to clean mailbox.',
  },
  553: {
    title: 'Mailbox name not allowed',
    meaning: 'The mailbox name (address) is invalid or not allowed by the receiving server (e.g. syntax or policy).',
    action: 'Verify address format and recipient server policy.',
  },
  554: {
    title: 'Transaction failed',
    meaning: 'The SMTP transaction failed. Often used for policy rejection, spam, or permanent failure.',
    action: 'Check content and reputation. For clients: confirm they are not blocked or blacklisted.',
  },
  555: {
    title: 'MAIL FROM / RCPT TO not recognized',
    meaning: 'The parameters supplied in MAIL FROM or RCPT TO are not recognized or supported by the server.',
    action: 'Verify address syntax and that extended parameters are supported by the recipient server.',
  },
};

export function getErrorExplanation(code) {
  const c = String((code && code.replace && code.replace(/\D/g, '')) || code);
  return SMTP_ERROR_EXPLANATIONS[c] || {
    title: 'Unknown or custom error',
    meaning: 'This SMTP or system error code is not in the standard reference. Check the raw message for details.',
    action: 'Review server logs and contact infrastructure if needed.',
  };
}
