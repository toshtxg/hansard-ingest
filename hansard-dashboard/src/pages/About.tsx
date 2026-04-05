import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function About() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-navy mb-2">About</h1>
        <p className="text-gray-600">Information about this project and how the data was collected and processed.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Data Source</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-gray-700">
          <p>
            All parliamentary speech data is sourced from the official{' '}
            <a
              href="https://sprs.parl.gov.sg"
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal hover:underline"
            >
              Singapore Parliament Reports System (SPRS)
            </a>
            , which publishes the official Hansard records of all parliamentary sittings.
          </p>
          <p>
            The Hansard is an official record of proceedings in the Singapore Parliament, covering oral and written questions,
            bills, debates, and ministerial statements. This explorer covers Parliaments 12 through 15.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Methodology</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-gray-700">
          <p>
            Speeches were extracted from the SPRS website and ingested into a structured database. Each speech is
            attributed to a named speaker and categorised by section type (oral speech, written answer, bill proceedings, etc.).
          </p>
          <p>
            Word counts are computed from the raw speech text. Sittings are identified by date. Where multiple speeches
            by the same MP occur in a single sitting, they are counted separately.
          </p>
          <p>
            Section types used in this explorer:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>OS</strong> — Oral Speech: speeches delivered in the chamber</li>
            <li><strong>OA</strong> — Oral Answer: answers to oral questions from MPs</li>
            <li><strong>WA</strong> — Written Answer: answers submitted in writing to parliamentary questions</li>
            <li><strong>WANA</strong> — Written Answer (Not Answered)</li>
            <li><strong>BP</strong> — Bill Proceedings: debate on bills</li>
            <li><strong>BI</strong> — Bill Introduction</li>
            <li><strong>WS</strong> — Written Statement</li>
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            AI-Generated Content <Badge variant="ai">AI-generated</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-gray-700">
          <p>
            Some content in this explorer is AI-generated, including one-line summaries of individual speeches and
            thematic labels for topics. These are marked with an <Badge variant="ai" className="text-xs">AI-generated</Badge> badge.
          </p>
          <p>
            AI summaries are generated using large language models and may contain errors or mischaracterisations.
            They are provided for convenience and should not be treated as authoritative representations of what was said.
            Always refer to the official Hansard for the exact text of speeches.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Limitations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-gray-700">
          <ul className="list-disc pl-5 space-y-2">
            <li>Data may not be complete or fully up to date — ingestion is periodic, not real-time.</li>
            <li>Speaker attribution relies on the structure of the official Hansard and may occasionally be incorrect.</li>
            <li>Word counts are approximate and depend on how text was extracted from source documents.</li>
            <li>Comparisons between MPs should be interpreted carefully — activity levels depend on role, portfolio, and tenure.</li>
            <li>No ranking or scoring of MPs is intended or implied.</li>
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Disclaimer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-gray-700">
          <p>
            This is an independent research project and is not affiliated with, endorsed by, or connected to the
            Singapore Government or Singapore Parliament in any way.
          </p>
          <p>
            All data presented is sourced from publicly available official records. This explorer is provided for
            informational and research purposes only. No commercial use is intended.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
