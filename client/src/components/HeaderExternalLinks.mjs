import { createElement } from 'react'


export const HEADER_LINKS = [
  { label: 'Discord', url: 'https://discord.gg/Bd3TxddY8n' },
  { label: 'Start.gg', url: 'https://www.start.gg/RES' },
]


export default function HeaderExternalLinks({ className }) {
  return HEADER_LINKS.map(link => createElement(
    'a',
    {
      key: link.url,
      href: link.url,
      target: '_blank',
      rel: 'noreferrer',
      className,
      'aria-label': `${link.label} (opens in a new tab)`,
    },
    link.label,
    createElement('span', { 'aria-hidden': true }, ' ↗'),
  ))
}
