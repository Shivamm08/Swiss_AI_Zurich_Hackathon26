import { useLlmModels } from '../api/hooks'
import type { LlmModels } from '../api/types'
import { HEURISTIC, useSelectedModel } from '../model/context'

const PROVIDER_LABELS: Record<LlmModels['models'][number]['provider'], string> = {
  openai: 'OpenAI',
  azure: 'Azure OpenAI',
  apertus: 'Swisscom · Apertus (Swiss open model)',
}

export default function ModelPicker() {
  const { data } = useLlmModels()
  const { model, setModel } = useSelectedModel()
  if (!data) return null

  return (
    <label className="flex items-center gap-2 text-xs text-slate-300" htmlFor="model-picker">
      Model
      <select
        id="model-picker"
        value={model ?? ''}
        onChange={(e) => setModel(e.target.value || undefined)}
        className="rounded-md border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white"
      >
        <option value="">{data.default_model ? `Default (${data.default_model})` : 'No LLM configured'}</option>
        {(Object.keys(PROVIDER_LABELS) as (keyof typeof PROVIDER_LABELS)[]).map((provider) => {
          const options = data.models.filter((m) => m.provider === provider && m.id !== data.default_model)
          return options.length === 0 ? null : (
            <optgroup key={provider} label={PROVIDER_LABELS[provider]}>
              {options.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </optgroup>
          )
        })}
        <option value={HEURISTIC}>Heuristic (no LLM)</option>
      </select>
    </label>
  )
}
