import styles from './About.module.css'

function Section({ title, children }) {
  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>{title}</h2>
      <div className={styles.body}>{children}</div>
    </section>
  )
}

function PointsTable() {
  const rows = [
    ['≤ −1', '1', 'Attended, underperformed seed'],
    ['0',    '2', 'Placed your seed'],
    ['+1',   '3', 'One round better than seeded'],
    ['+2',   '5', 'Two rounds better than seeded'],
    ['+3',   '10', 'Three rounds better than seeded'],
    ['+4',   '15', 'Four rounds better'],
    ['+5',   '20', '+5 pts per additional round above that'],
  ]
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th>SPR</th>
          <th>Points</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([spr, pts, desc]) => (
          <tr key={spr}>
            <td className={spr.startsWith('+') ? styles.positive : spr.startsWith('≤') ? styles.muted : ''}>{spr}</td>
            <td className={styles.pts}>{pts}</td>
            <td className={styles.desc}>{desc}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function About() {
  return (
    <div className={styles.root}>
      <Section title="Welcome to RESONANCE">
        <p>
          RESONANCE is a WWA Crew League built around player improvement, community building,
          and mutual support. Teams of players at varied skill levels compete across local
          tournaments, earning points through attendance and performance — not raw skill alone.
        </p>
        <p>
          Have you ever felt like your tournament placements weren't moving the needle?
          That's what Resonance is for. Every set you play now helps your team, and your
          teammates are invested in your growth too.
        </p>
      </Section>

      <Section title="How Points Work">
        <p>
          Points are based on <strong>Seed Performance Rating (SPR)</strong> — how many bracket
          rounds better or worse you placed compared to your seed. Showing up earns you something.
          Outperforming earns you more.
        </p>
        <PointsTable />
      </Section>

      <Section title="Season Format">
        <p>
          Season 1 runs for 6 weeks across WWA locals, culminating in a finale crew battle in
          Redmond, WA. 8 teams of 5 (captain + 4 draftees). The draft is snake-order, streamed
          in the official Discord.
        </p>
        <p>
          The team with the most points at the end of the regular season chooses their first
          opponent in the finale bracket. Once the crew battle starts — anyone can win.
        </p>
        <p>
          Top 4 teams at the finale receive prize pool payouts. The champions take home the first
          ever RESONANCE Champion trophy.
        </p>
      </Section>

      <Section title="Season 1 Captains">
        <ul className={styles.captains}>
          {['Graves', 'Stiv', 'Chango', 'Melo', 'SpiritGun', 'Jontae', 'Shanks', 'Browndogsarecool42'].map(c => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </Section>

      <Section title="Questions?">
        <p>
          Reach out to head TO <strong>Rome0</strong> on Discord (<code>rome0.</code>) for
          registration questions or to inquire about being a captain next season.
        </p>
      </Section>
    </div>
  )
}
