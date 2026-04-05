import { useState, useEffect, useCallback, useRef } from 'react'
import { supabase } from '../lib/supabase'

interface RpcState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useSupabaseRpc<T>(
  fnName: string,
  params?: Record<string, unknown>,
  deps?: unknown[]
): RpcState<T> & { refetch: () => void } {
  const [state, setState] = useState<RpcState<T>>({ data: null, loading: true, error: null })
  const paramsRef = useRef(params)
  paramsRef.current = params

  const fetch = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }))
    const { data, error } = await supabase.rpc(fnName, paramsRef.current ?? {})
    if (error) setState({ data: null, loading: false, error: error.message })
    else setState({ data: data as T, loading: false, error: null })
  }, [fnName, ...(deps ?? [])]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void fetch() }, [fetch])

  return { ...state, refetch: fetch }
}
