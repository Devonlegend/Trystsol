use anchor_lang::prelude::*;

#[derive(AnchorSerialize, AnchorDeserialize, InitSpace, Clone, Copy, PartialEq, Eq, Debug)]
pub enum LifecycleStatus {
    Active,
    Completed,
    Suspended,
}

#[derive(AnchorSerialize, AnchorDeserialize, InitSpace, Clone, Copy, PartialEq, Eq, Debug)]
pub enum MilestoneStatus {
    Pending,
    Submitted,
    UnderReview,
    Verified,
    Rejected,
}

#[derive(AnchorSerialize, AnchorDeserialize, InitSpace, Clone, Copy, PartialEq, Eq, Debug)]
pub enum Decision {
    Verify,
    Reject,
}

#[account]
#[derive(InitSpace, Debug)]
pub struct Registry {
    pub admin: Pubkey,
    pub pending_admin: Option<Pubkey>,
    pub reviewer_count: u16,
    pub schema_version: u16,
    pub bump: u8,
}

#[account]
#[derive(InitSpace, Debug)]
pub struct Reviewer {
    pub wallet: Pubkey,
    pub active: bool,
    pub added_at: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace, Debug)]
pub struct Project {
    pub authority: Pubkey,
    pub pending_authority: Option<Pubkey>,
    pub metadata_hash: [u8; 32],
    #[max_len(128)]
    pub metadata_uri: String,
    pub lifecycle_status: LifecycleStatus,
    pub created_at: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace, Debug)]
pub struct CriteriaTemplate {
    pub template_id: [u8; 16],
    pub version: u16,
    pub criteria_hash: [u8; 32],
    #[max_len(128)]
    pub criteria_uri: String,
    pub published_by: Pubkey,
    pub active: bool,
    pub created_at: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace, Debug)]
pub struct Milestone {
    pub project: Pubkey,
    pub milestone_id: [u8; 16],
    pub round: u16,
    pub evidence_hash: [u8; 32],
    #[max_len(128)]
    pub evidence_uri: String,
    pub criteria_hash: [u8; 32],
    #[max_len(128)]
    pub criteria_uri: String,
    pub criteria_template_id: [u8; 16],
    pub criteria_version: u16,
    #[max_len(5)]
    pub assigned_reviewers: Vec<Pubkey>,
    pub required_approvals: u8,
    pub approvals: u8,
    pub rejections: u8,
    pub status: MilestoneStatus,
    pub submitted_at: i64,
    pub finalized_at: i64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace, Debug)]
pub struct Verification {
    pub milestone: Pubkey,
    pub round: u16,
    pub reviewer: Pubkey,
    pub decision: Decision,
    pub evidence_hash: [u8; 32],
    pub criteria_hash: [u8; 32],
    pub timestamp: i64,
    pub bump: u8,
}
