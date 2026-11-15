export interface User{id:number;email:string;name:string;role:'admin'|'analyst'|'viewer'}
export interface Study{id:number;code:string;name:string;protocol:string;source_file:string}
export interface Treatment{id:number;study_id?:number;code:string;name:string;process_note:string}
export interface ReadingQuality{excluded:boolean;notice_ids:number[];notice_titles:string[];reason:string}
export interface Reading{id:number;study_id?:number;treatment_id:number;specimen_code:string;grade:number;source_note:string;pooled_rank?:number;quality?:ReadingQuality}
export interface Group extends Treatment{n:number;rank_sum:number;mean_rank:number;median_lower:number;median_upper:number;grade_counts:Record<string,number>}
export interface Pair{i:number;j:number;left_code:string;right_code:string;left_name:string;right_name:string;mean_rank_difference:number;standard_error:number;z:number;p_raw_asymptotic:number;p_holm:number;reject:boolean}
export interface Exclusion{specimen_code:string;treatment_code:string;treatment_name:string;grade:number;notice_ids:number[];notice_titles:string[];reason:string}
export interface QualityBasis{run_id:number;basis_status:'current'|'invalidated';invalidated:boolean;invalidated_by_notice_ids:number[];invalidated_notices?:{id:number;title:string;status:string}[];invalidated_reason:string;exclusion_count:number;exclusion_fingerprint:string;applied_notice_ids:number[];hit_specimen_codes:string[];frozen_specimen_count:number}
export interface Snapshot{study:Study;treatments:Treatment[];readings:Reading[];exclusions?:Exclusion[];applied_notice_ids?:number[]}
export interface Result{n:number;k:number;h_raw:number;h:number;df:number;p_asymptotic:number;p_underflow:boolean;tie_term:number;tie_correction:number;dunn_variance:number;ties:{grade:number;count:number;average_rank:number;term:number}[];groups:Group[];pairs:Pair[];ranked_readings:Reading[];alpha:number;omnibus_reject:boolean;family_size:number;fingerprint:string;p_method:string;snapshot:Snapshot}
export interface Run{id:number;study_id:number;name:string;alpha:number;status:'queued'|'running'|'completed'|'failed';snapshot:Snapshot;result:Result;error:string;created_at:string;quality:QualityBasis;exclusions:Exclusion[]}
export interface Note{id:number;name:string;run_id:number;rationale:string;status:'draft'|'approved'|'rejected';reviewer_note:string;reviewed_by:string;created_at:string;quality:QualityBasis}
export interface NoticeItem{study_id:number;study_code?:string;specimen_code:string;treatment_code?:string;treatment_name?:string}
export interface QualityNotice{id:number;title:string;reason:string;items:NoticeItem[];status:'active'|'revoked';issued_by:string;created_at:string;revoked_by:string;revocation_reason:string;revoked_at:string|null;affected_run_ids:number[]}
