import fs from 'node:fs'
import path from 'node:path'

function escapeXml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

function getBadgeColor(percentage) {
  if (percentage >= 90) return '#2ea043'
  if (percentage >= 80) return '#3fb950'
  if (percentage >= 70) return '#9a6700'
  if (percentage >= 60) return '#d29922'
  return '#cf222e'
}

function getTextWidth(text) {
  return text.length * 7 + 10
}

const [, , summaryPath, outputPath, badgeLabel] = process.argv

if (!summaryPath || !outputPath) {
  console.error(
    'Usage: node scripts/generate-coverage-badge.mjs <coverage-summary.json> <output.svg> [label]',
  )
  process.exit(1)
}

const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf8'))

function getLineCoverage(summaryData) {
  if (summaryData?.total?.lines?.pct !== undefined) {
    return Number(summaryData.total.lines.pct)
  }

  if (summaryData?.totals?.percent_covered !== undefined) {
    return Number(summaryData.totals.percent_covered)
  }

  return Number.NaN
}

const lineCoverage = getLineCoverage(summary)

if (Number.isNaN(lineCoverage)) {
  console.error('Could not read total line coverage from the coverage summary.')
  process.exit(1)
}

const label = badgeLabel || 'frontend coverage'
const message = `${lineCoverage.toFixed(2)}%`
const labelWidth = getTextWidth(label)
const messageWidth = getTextWidth(message)
const totalWidth = labelWidth + messageWidth
const color = getBadgeColor(lineCoverage)
const labelCenter = labelWidth / 2
const messageCenter = labelWidth + messageWidth / 2

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${totalWidth}" height="20" role="img" aria-label="${escapeXml(label)}: ${escapeXml(message)}">
  <title>${escapeXml(label)}: ${escapeXml(message)}</title>
  <linearGradient id="smooth" x2="0" y2="100%">
    <stop offset="0" stop-color="#ffffff" stop-opacity=".7"/>
    <stop offset=".1" stop-color="#aaaaaa" stop-opacity=".1"/>
    <stop offset=".9" stop-color="#000000" stop-opacity=".3"/>
    <stop offset="1" stop-color="#000000" stop-opacity=".5"/>
  </linearGradient>
  <clipPath id="clip">
    <rect width="${totalWidth}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#clip)">
    <rect width="${labelWidth}" height="20" fill="#555"/>
    <rect x="${labelWidth}" width="${messageWidth}" height="20" fill="${color}"/>
    <rect width="${totalWidth}" height="20" fill="url(#smooth)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="${labelCenter}" y="15" fill="#010101" fill-opacity=".3">${escapeXml(label)}</text>
    <text x="${labelCenter}" y="14">${escapeXml(label)}</text>
    <text x="${messageCenter}" y="15" fill="#010101" fill-opacity=".3">${escapeXml(message)}</text>
    <text x="${messageCenter}" y="14">${escapeXml(message)}</text>
  </g>
</svg>
`

fs.mkdirSync(path.dirname(outputPath), { recursive: true })
fs.writeFileSync(outputPath, svg)

console.log(`Wrote ${label} badge to ${outputPath}`)
