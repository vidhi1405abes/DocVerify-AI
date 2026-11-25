const Footer = () => (
  <footer className="mt-16 border-t border-gray-200 bg-white">
    <div className="container mx-auto flex flex-col gap-2 px-4 py-6 text-sm text-gray-500 md:flex-row md:justify-between">
      <p>© {new Date().getFullYear()} DocVerify AI · Intelligent document verification and fraud detection</p>
      <p>Results support human verifiers and are not proof of official authenticity.</p>
    </div>
  </footer>
)

export default Footer
