use anchor_lang::prelude::*;

#[error_code]
pub enum RegistryError {
    #[msg("Only the registry admin may perform this action.")]
    UnauthorizedAdmin,
    #[msg("URI must not be empty.")]
    UriEmpty,
    #[msg("URI exceeds the maximum length of 128 bytes.")]
    UriTooLong,
    #[msg("Between 1 and 5 reviewers are required.")]
    InvalidReviewerCount,
    #[msg("Duplicate reviewer in the assignment list.")]
    DuplicateReviewer,
    #[msg("Required approvals must be between 1 and the reviewer count.")]
    InvalidApprovals,
    #[msg("Reviewer is not active.")]
    ReviewerInactive,
    #[msg("Reviewer is not assigned to this milestone.")]
    ReviewerNotAssigned,
    #[msg("A project authority cannot review its own milestone.")]
    AuthorityCannotReview,
    #[msg("Milestone is not in a valid state for this action.")]
    InvalidMilestoneStatus,
    #[msg("Round counter overflow.")]
    RoundOverflow,
    #[msg("Reviewers must be assigned before submission.")]
    ReviewersNotAssigned,
    #[msg("Reviewer account does not match the signer or the registry.")]
    ReviewerMismatch,
    #[msg("Registry schema version mismatch.")]
    SchemaMismatch,
    #[msg("Project or milestone ID must not be all zeroes.")]
    InvalidIdentifier,
    #[msg("Project is not active.")]
    ProjectNotActive,
    #[msg("Evidence or criteria hash is missing.")]
    MissingHash,
    #[msg("Criteria template is invalid or inactive.")]
    InvalidCriteria,
    #[msg("Reviewer assignment cannot change after a verdict in this round.")]
    ReassignmentLocked,
    #[msg("Milestone is not in a state that can be expired.")]
    InvalidRoundState,
    #[msg("Reviewer is already inactive.")]
    ReviewerAlreadyInactive,
    #[msg("No pending authority transfer exists for this signer.")]
    NoPendingAuthority,
    #[msg("No pending registry admin transfer exists for this signer.")]
    NoPendingAdmin,
}
