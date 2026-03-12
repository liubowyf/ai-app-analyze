export default function Loading() {
  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      <div className="max-w-[1600px] mx-auto space-y-6 animate-pulse">
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
          <div className="h-8 w-64 bg-slate-200 rounded-lg" />
          <div className="h-4 w-96 bg-slate-100 rounded-lg mt-3" />
        </div>

        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex flex-col sm:flex-row gap-3">
          <div className="h-10 flex-1 bg-slate-100 rounded-lg" />
          <div className="h-10 w-full sm:w-36 bg-slate-100 rounded-lg" />
          <div className="h-10 w-full sm:w-36 bg-slate-100 rounded-lg" />
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="h-14 bg-slate-50 border-b border-slate-200" />
          <div className="space-y-3 p-6">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="h-14 bg-slate-50 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
