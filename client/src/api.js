export async function requestJson(url, options = {}) {
  let response
  try {
    response = await fetch(url, options)
  } catch {
    throw new Error('Network request failed. Check your connection and try again.')
  }

  let text
  try {
    text = await response.text()
  } catch {
    throw new Error('The server response could not be read. Please try again.')
  }
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      if (response.ok) {
        throw new Error('The server returned an invalid response. Please try again.')
      }
    }
  }

  if (!response.ok) {
    const message = data?.error || `Request failed with status ${response.status}.`
    const error = new Error(message)
    error.status = response.status
    error.data = data
    throw error
  }

  return data
}
