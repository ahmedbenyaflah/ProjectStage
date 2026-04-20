// SMTP error codes for support: what they mean and suggested actions
// Used in telecom / agency SMTP flow logs for anomaly detection
export const SMTP_ERROR_EXPLANATIONS = {
  421: {
    title: 'Service not available',
    meaning: 'The receiving server is temporarily refusing connections (e.g. overloaded or in maintenance). The transmission channel was closed.',
    action: 'Retry later. If it persists, check recipient server status or contact their postmaster.',
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
};

export function getErrorExplanation(code) {
  const c = String((code && code.replace && code.replace(/\D/g, '')) || code);
  return SMTP_ERROR_EXPLANATIONS[c] || {
    title: 'Unknown or custom error',
    meaning: 'This SMTP or system error code is not in the standard reference. Check the raw message for details.',
    action: 'Review server logs and contact infrastructure if needed.',
  };
}

