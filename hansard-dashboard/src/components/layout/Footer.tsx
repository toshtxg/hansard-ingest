export function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="bg-gray-50 border-t mt-16">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 text-sm text-gray-500">
          <div className="space-y-1">
            <p>
              Data sourced from{' '}
              <a
                href="https://sprs.parl.gov.sg"
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal hover:underline"
              >
                Singapore Parliament Hansard
              </a>
            </p>
            <p>Independent project, not affiliated with the Singapore Government.</p>
          </div>
          <div className="flex flex-col items-start sm:items-end gap-1">
            <p>&copy; {year} SG Hansard Explorer</p>
          </div>
        </div>
      </div>
    </footer>
  )
}
