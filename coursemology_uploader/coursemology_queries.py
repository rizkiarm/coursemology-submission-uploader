"""Coursemology API query utilities for assessments, questions, and answers."""

from __future__ import annotations

import re

from coursemology_py.api.course.assessments import AssessmentAPI
from coursemology_py.api.course.submissions import AssessmentSubmissionsAPI
from coursemology_py.models.course.assessment.categories import CategoryBasic
from coursemology_py.models.course.assessments import AssessmentListData
from coursemology_py.models.course.submissions import (
    AssessmentSubmission,
    ProgrammingAnswerInfo,
    QuestionInfo,
    SubmissionEditData,
)
from coursemology_py.models.course.users import CourseUser


def get_student_submissions(
    submissions_api: AssessmentSubmissionsAPI,
    students: list[CourseUser],
) -> list[AssessmentSubmission]:
    """Fetch submissions belonging to the provided students.

    Args:
        submissions_api: API for the target assessment submissions.
        students: Students to include.

    Returns:
        List of AssessmentSubmission for the specified students.
    """
    submissions = submissions_api.index().submissions
    student_ids = {student.id for student in students}
    return [s for s in submissions if s.course_user.id in student_ids]


def _find_by_title[T](items: list[T], title: str, title_attr: str, item_type: str) -> T:
    """Generic helper to find an item by its title attribute.

    Args:
        items: List of items to search.
        title: Target title to find.
        title_attr: Attribute name containing the title.
        item_type: Type name for error messages.

    Returns:
        The matching item.

    Raises:
        ValueError: If the item is not found.
    """
    for item in items:
        if getattr(item, title_attr) == title:
            return item
    raise ValueError(f"{item_type} with title '{title}' not found.")


def get_category(assessment_api: AssessmentAPI, category_title: str) -> CategoryBasic:
    """Find an assessment category by its title.

    Args:
        assessment_api: Assessment API client.
        category_title: Title of the category.

    Returns:
        The matching category object.

    Raises:
        ValueError: If the category is not found.
    """
    categories = assessment_api.categories.index().categories
    return _find_by_title(categories, category_title, "title", "Category")


def get_assessment(
    assessment_api: AssessmentAPI,
    category_id: int,
    assessment_title: str,
) -> AssessmentListData:
    """Find an assessment by title within a category.

    Args:
        assessment_api: Assessment API client.
        category_id: ID of the parent category.
        assessment_title: Target assessment title.

    Returns:
        The matching assessment object.

    Raises:
        ValueError: If the assessment is not found.
    """
    assessments = assessment_api.assessments.index(category_id).assessments
    try:
        return _find_by_title(assessments, assessment_title, "title", "Assessment")
    except ValueError as e:
        raise ValueError(f"Assessment with title '{assessment_title}' not found in category ID {category_id}.") from e


def get_question_key(filename: str, file_question_map: dict[str, str]) -> str | None:
    """Return the regex key in file_question_map that matches the filename.

    Args:
        filename: The filename to match.
        file_question_map: Mapping of regex/string pattern to question title.

    Returns:
        The matching pattern key, or None if no pattern matches.
    """
    for pattern in file_question_map.keys():
        if re.match(pattern, filename):
            return pattern
    return None


def get_question(questions: list[QuestionInfo], title: str) -> QuestionInfo:
    """Find a question by its title.

    Args:
        questions: List of QuestionInfo objects.
        title: Target question title.

    Returns:
        The matching QuestionInfo object.

    Raises:
        ValueError: If the question is not found.
    """
    return _find_by_title(questions, title, "question_title", "Question")


def get_answer(answers: list[ProgrammingAnswerInfo], answer_id: int) -> ProgrammingAnswerInfo:
    """Find a programming answer by its ID.

    Args:
        answers: List of ProgrammingAnswerInfo objects.
        answer_id: Target answer ID.

    Returns:
        The matching ProgrammingAnswerInfo object.

    Raises:
        ValueError: If the answer is not found.
    """
    for answer in answers:
        if answer.id == answer_id:
            return answer
    raise ValueError(f"Answer with ID '{answer_id}' not found.")


def get_question_answer(
    submission_edit: SubmissionEditData,
    question_title: str,
) -> ProgrammingAnswerInfo:
    """Get the programming answer for a specific question title in a submission.

    Args:
        submission_edit: The editable assessment submission.
        question_title: The target question title.

    Returns:
        The corresponding ProgrammingAnswerInfo object.

    Raises:
        ValueError: If the question or answer is not found, or if question has no answer ID.
    """
    question = get_question(submission_edit.questions, question_title)
    if question.answer_id is None:
        raise ValueError(f"Question '{question_title}' has no associated answer ID.")
    return get_answer(submission_edit.answers, question.answer_id)  # pyright: ignore[reportArgumentType]
