import { useLlmModels } from '../api/hooks'
import { HEURISTIC, useSelectedModel } from '../model/context'

export default function ModelPicker() {
  const { data } = useLlmModels()
  const { model, setModel } = useSelectedModel()
  if (!data) return null

  return (
    <label className="flex flex-col gap-1 text-xs text-slate-500" htmlFor="model-picker">
      AI model
      <select
        id="model-picker"
        value={model ?? ''}
        onChange={(e) => setModel(e.target.value || undefined)}
        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900"
      >
        <option value="">{data.default_model ? `Default (${data.default_model})` : 'No LLM configured'}</option>
        {data.models
          .filter((m) => m !== data.default_model)
          .map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        <option value={HEURISTIC}>Heuristic (no LLM)</option>
      </select>
    </label>
  )
}
