import asyncio
from typing import Any

from zen_bangumi.effects.result import EffectResult, EffectStatus


class EffectInterpreter:
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._executed_keys: set[str] = set()

    async def execute(self, commands: list[Any]) -> list[EffectResult]:
        results = []
        
        for command in commands:
            key = command.idempotency_key
            
            if key in self._executed_keys:
                results.append(EffectResult(
                    command=command,
                    status=EffectStatus.SKIPPED,
                ))
                continue
            
            result = await self._execute_with_retry(command)
            results.append(result)
            
            if result.status == EffectStatus.SUCCESS:
                self._executed_keys.add(key)
        
        return results

    async def _execute_with_retry(self, command: Any) -> EffectResult:
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                await self._dispatch(command)
                return EffectResult(
                    command=command,
                    status=EffectStatus.SUCCESS,
                )
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        return EffectResult(
            command=command,
            status=EffectStatus.FAILED,
            error=last_error,
        )

    async def _dispatch(self, command: Any) -> None:
        match command:
            case _:
                raise NotImplementedError(
                    f"No adapter implemented for {type(command).__name__}"
                )
