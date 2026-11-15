import {request,post} from './client';import type {QualityNotice} from '../types/domain';
export const list=(study_id?:number)=>request<QualityNotice[]>('/notices'+(study_id?`?study_id=${study_id}`:''));
export const create=(data:unknown)=>post<{notice:QualityNotice;invalidated_run_ids:number[]}>('/notices',data);
export const revoke=(id:number,reason:string)=>post<QualityNotice>('/notices/'+id+'/revoke',{reason});
