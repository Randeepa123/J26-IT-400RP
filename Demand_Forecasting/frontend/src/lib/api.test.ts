import { describe, expect, it, vi, afterEach } from 'vitest'
import { csvText, filterParams, request } from './api'
import { date, epoch, value } from './format'
import type { Filters } from './types'

afterEach(()=>vi.unstubAllGlobals())
describe('research data client',()=>{
 it('retains every selected regime and inclusive date parameters',()=>{
  const filters:Filters={start:'2022-01-01',end:'2022-02-01',regimes:['pre_crisis','crisis'],classification:'all',match:'all',model:'adapted'}
  expect(filterParams(filters).getAll('regimes')).toEqual(['pre_crisis','crisis'])
  expect(filterParams(filters).get('end_date')).toBe('2022-02-01')
 })
 it('displays Sri Lankan local timestamps without browser timezone shifts',()=>{
  expect(epoch('2022-01-01T00:00:00')).toBe(Date.parse('2021-12-31T18:30:00Z'))
  expect(date('2022-01-01T00:00:00')).toContain('01 Jan 2022')
  expect(date('2022-01-01')).toContain('01 Jan 2022')
  expect(date('not a date')).toBe('Not available')
  expect(value(null)).toBe('—')
 })
 it('exports complete escaped CSV and prevents spreadsheet formulas',()=>{
  const csv=csvText([{timestamp:'2022-01-01',note:'="unsafe"',value:0},{timestamp:'2022-01-02',note:'a,b',value:null}])
  expect(csv).toContain('"\'=""unsafe"""')
  expect(csv).toContain('"a,b"')
  expect(csv).toContain('"0"')
 })
 it('surfaces structured API errors instead of presenting fake results',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:503,json:async()=>({error:{message:'Model artifacts unavailable'}})}))
  await expect(request('/forecast')).rejects.toThrow('Model artifacts unavailable')
 })
 it('handles an HTML response from a misconfigured proxy',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>{throw new Error('HTML')}}))
  await expect(request('/health')).rejects.toThrow('unreadable response')
 })
})
